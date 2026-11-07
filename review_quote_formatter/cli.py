"""Command-line interface: paste reviews, get honest pull quotes."""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

from . import __version__
from .extraction import Quote, extract_quotes, trim_quote
from .emit import EmitOptions, write_quote_sheet, write_retail_blurb, write_social_cards
from .parser import parse_reviews
from .provenance import build_record, input_sha256, write_provenance
from .style import bracketed_initial_cap, caps_pass, normalize_ellipsis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reviewquote",
        description=(
            "Turn pasted book reviews into short, attributed pull quotes with honest,"
            " logged trimming, house-style caps/ellipsis rules, quote sheets,"
            " social-card text, and retail-ready editorial blurbs."
        ),
    )
    parser.add_argument("-i", "--input", required=True, help="path to pasted review text, or '-' for stdin")
    parser.add_argument("-o", "--outdir", default="out", help="output directory (default: ./out)")
    parser.add_argument("--title", default="your book", help="book title used in the quote sheet/blurb")
    parser.add_argument("--max-words", type=int, default=16, help="max words per pull quote (default 16)")
    parser.add_argument("--top", type=int, default=5, help="number of quotes to emit (default 5)")
    parser.add_argument("--max-per-review", type=int, default=2, help="max quotes per single review (default 2)")
    parser.add_argument("--social-limit", type=int, default=280, help="social card character budget (default 280)")
    parser.add_argument("--ascii-ellipsis", action="store_true", help='use "..." instead of the ... glyph')
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def style_run(original: str, max_words: int, ascii_ellipsis: bool) -> tuple[str, list[str], int]:
    """Trim + house-style one candidate sentence. Returns (text, transformations, words_dropped)."""
    text, transformations, dropped = trim_quote(original, max_words, ascii_ellipsis)
    caps, changes = caps_pass(text)
    transformations.extend(changes)
    bracketed, changes = bracketed_initial_cap(caps)
    transformations.extend(changes)
    final, changes = normalize_ellipsis(bracketed, ascii_ellipsis)
    transformations.extend(changes)
    return final, _dedupe(transformations), dropped


def fit_for_social(quote: Quote, limit: int, base_max_words: int, ascii_ellipsis: bool) -> tuple[Quote, list[str]]:
    """Return a quote whose social card fits the character budget.

    Tries shorter attributions, then progressively tighter honest trims.
    If even the honest minimum cannot fit, the closest-fit variant is used
    and the compromise is logged (``social_limit_exceeded``). Never
    invents or removes quoted words beyond the logged trimming rules.
    """
    attributions = [quote.attribution()]
    if quote.source.reviewer:
        attributions.append(quote.source.reviewer)
    attributions.append("verified reader")

    def card_len(text: str, attribution: str) -> int:
        return len(f'"{text}"\n— {attribution}\n')

    fit = copy.copy(quote)
    fit.transformations = list(quote.transformations)
    fit.dropped_words = quote.dropped_words
    fit.attribution_override = None
    notes: list[str] = []
    if card_len(quote.text, attributions[0]) <= limit:
        return fit, notes

    best: tuple[str, str, int, list[str], int] | None = None  # (text, attribution, len, transformations, dropped)
    for attribution in attributions[1:]:
        if card_len(quote.text, attribution) <= limit:
            fit.attribution_override = attribution
            fit.transformations.append("social_shortened_attribution")
            return fit, notes
        for mw in range(base_max_words - 2, 3, -2):
            text, transformations, dropped = style_run(quote.original, mw, ascii_ellipsis)
            length = card_len(text, attribution)
            if len(text.split()) < 2:
                continue
            if best is None or length < best[2]:
                best = (text, attribution, length, transformations, dropped)
            if length <= limit:
                fit.text = text
                fit.dropped_words = dropped
                fit.attribution_override = attribution
                fit.transformations = transformations + ["social_shortened"]
                return fit, notes
    if best is not None:
        fit.text, fit.attribution_override, fit.dropped_words, fit.transformations = best[0], best[1], best[4], best[3]
        fit.transformations.append("social_limit_exceeded")
        notes.append("social_limit_exceeded")
    else:
        notes.append("social_limit_exceeded")
    return fit, notes


def _dedupe(transformations: list[str]) -> list[str]:
    seen: list[str] = []
    for item in transformations:
        if item not in seen:
            seen.append(item)
    return seen


def run(args: argparse.Namespace) -> int:
    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"error: input file not found: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8-sig")
    if not raw.strip():
        print("error: input is empty", file=sys.stderr)
        return 1

    blocks = parse_reviews(raw)
    if not blocks:
        print("error: could not parse any review blocks from input", file=sys.stderr)
        return 1

    hash_prefix = input_sha256(raw)
    picked = extract_quotes(blocks, top=args.top, max_per_review=args.max_per_review, max_words=args.max_words)
    if not picked:
        print("error: no pull-quote-worthy sentences found (need clearly positive sentences)", file=sys.stderr)
        return 2

    for quote in picked:
        text, transformations, dropped = style_run(quote.original, args.max_words, args.ascii_ellipsis)
        quote.text = text
        quote.transformations = transformations
        quote.dropped_words = dropped

    social_quotes = []
    social_notes: list[str] = []
    for quote in picked:
        fitted, notes = fit_for_social(quote, args.social_limit, args.max_words, args.ascii_ellipsis)
        social_quotes.append(fitted)
        social_notes.append(notes[0] if notes else "")

    outdir = Path(args.outdir)
    options = EmitOptions(title=args.title, social_limit=args.social_limit)
    quote_sheet = write_quote_sheet(picked, options, outdir / "quote_sheet.md", hash_prefix)
    cards_dir = write_social_cards(social_quotes, options, outdir)
    blurb = write_retail_blurb(picked, options, outdir / "retail_blurb.md")
    records = []
    for quote, social_quote, note in zip(picked, social_quotes, social_notes):
        record = build_record(quote, hash_prefix)
        if social_quote.attribution_override:
            record["social_attribution"] = social_quote.attribution_override
        if note:
            record["transformations"].append(note)
        records.append(record)
    provenance_path = write_provenance(records, hash_prefix, outdir / "provenance.json")

    print(f"extracted {len(picked)} quote(s) from {len(blocks)} review block(s)")
    print(f"quote sheet:   {quote_sheet}")
    print(f"social cards:  {cards_dir}")
    print(f"retail blurb:  {blurb}")
    print(f"provenance:    {provenance_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)
