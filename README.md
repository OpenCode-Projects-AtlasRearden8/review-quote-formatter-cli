# review-quote-formatter-cli

Turn pasted book reviews into honest, attributed pull quotes — fast, offline, local-first.

Built by **Asdale Dynamics, LLC** (Dylan Asdale) as part of the beginner-friendly author
toolkit around *The Massive AI Manual* and [dylanasdale.github.io](https://dylanasdale.github.io).
Paste harvested review text (from Amazon, Goodreads, NetGalley, StoryGraph, etc.), and the tool
extracts short pull quotes, enforces a house style (caps and ellipsis rules), and emits:

- **quote_sheet.md** — numbered pull quotes with attributions and per-quote provenance notes
- **social/** — one text card per quote, trimmed to your character budget (default 280)
- **retail_blurb.md** — retail-ready editorial blurb built from the top three quotes
- **provenance.json** — a machine-readable log of every quote's source, line range, what was
  dropped, and every transformation applied

It runs 100% offline with the standard library only. It never publishes anything and never
calls a network.

Distinct from its sibling projects: **arc-review-tracker-webapp** (manages the ARC review
pipeline) and **book-promo-graphics-template** (turns finished quote text into visual cards).

## The honesty rules

Marketing pull quotes are easy to abuse; this tool is deliberately conservative:

1. **No leading ellipsis.** A quote always starts on real text.
2. **Cuts only at clause boundaries.** Words can only be dropped after a comma or
   sentence-ending punctuation — never mid-phrase.
3. **No dangling negation.** A kept region may never end on (or hide a `not` before) a
   keyword: "not love…" can never be quoted as "love…" and vice versa.
4. **Contrast protection.** Nothing is cut directly before a `but`/`however` clause, so a
   quote can't silently shed the criticism it sat next to in the original.
5. **Everything is logged.** Every dropped word count and every transformation appears in
   `provenance.json`, and the quote sheet marks trimmed quotes `human_review_required`.
   A human must verify each quote against its source before publication — the tool is an
   assistant, not a green light.

House style details: shouting words (`AMAZING`) are softened to Title Case (logged, acronyms
like `AI`/`KDP` preserved); lowercase quote starts get a bracketed capital (`[A]bsolutely`);
ellipsis is one glyph with no surrounding spaces (or `...` with `--ascii-ellipsis`).

## Install

```bash
pip install -e .        # Python 3.10+, no third-party dependencies
```

Or just run it from the repo without installing:

```bash
python3 -m review_quote_formatter -i reviews.txt -o out/
```

## Usage

```bash
reviewquote -i reviews.txt -o out/ --title "The Massive AI Manual"
```

Options:

| Flag | Default | Meaning |
|---|---|---|
| `-i/--input` | required | review text file, or `-` for stdin |
| `-o/--outdir` | `out` | output directory |
| `--title` | `your book` | title used in the quote sheet and blurb |
| `--max-words` | `16` | maximum words per quote |
| `--top` | `5` | how many quotes to select |
| `--max-per-review` | `2` | cap per source review for variety |
| `--social-limit` | `280` | character budget per social card |
| `--ascii-ellipsis` | off | use `...` instead of the `…` glyph |

Exit codes: `0` success, `1` input error, `2` no quote-worthy sentences found.

Input format: reviews separated by divider lines (`---`) or as separate pasted blocks, each
with optional metadata lines — a star rating (`★★★★★`, `5/5 stars`) and a reviewer line such
as `-- Jane D., Amazon`, `— Tom H., StoryGraph`, or `Dee W. | Goodreads`. See
`examples/sample_reviews.txt`. Unknown metadata stays in the body; attribution falls back to
"verified reader" when no reviewer is found.

## Reviewer attribution

The tool does not invent reviewers. If the reviewer line is missing or unparsable, the quote
is attributed to "verified reader" and the provenance log tells you exactly which review it
came from so you can fill in real names yourself.

## Development

```bash
python3 -m pytest          # 39 tests
```

Layout: `review_quote_formatter/` (parser, extraction/trimming, style, provenance, emit, cli),
`tests/`, `examples/sample_reviews.txt`.

## License

MIT — Copyright (c) 2026 Asdale Dynamics, LLC. See [LICENSE](LICENSE).

No secrets, API keys, or personal data are stored by this tool; everything stays in the
output folder you point it at.
