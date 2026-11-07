# STATUS — review-quote-formatter-cli

Last updated: 2026-11-07

## What was built

A fully offline Python CLI (`reviewquote` / `python -m review_quote_formatter`) that turns
pasted book-review text into honest, attributed marketing pull quotes:

- **Parser** (`review_quote_formatter/parser.py`): splits pasted reviews into blocks
  (divider lines or plain blocks), extracts star ratings, reviewer names, and platforms
  (Amazon, Goodreads, NetGalley, StoryGraph, etc.), and never invents attribution —
  unnamed reviews are attributed to "verified reader".
- **Extraction & honest trimming** (`extraction.py`): scores sentences for clearly positive
  keywords, then trims only at clause boundaries (comma/terminal punctuation). Guards:
  no leading ellipsis, no kept region ending on a negation, no cut that swallows or hides a
  `but`-clause, no quoting around negated keywords ("not love"). Sentences that cannot be
  trimmed honestly at the requested budget are skipped, never misquoted.
- **House style** (`style.py`): ALL-CAPS shouting softened to Title Case (logged; `AI`,
  `KDP`, `ARC`, etc. preserved as acronyms); lowercase quote starts get a bracketed
  editorial capital (`[A]bsolutely`); ellipsis canonized to one no-space glyph (or
  `--ascii-ellipsis` for `...`).
- **Outputs** (`emit.py`): `quote_sheet.md` (numbered quotes + attributions + provenance
  footnotes), `social/card-NN.txt` (one card per quote, fitted to `--social-limit` by
  first shortening attribution, then re-trimming honestly; unachievable budgets are logged
  as `social_limit_exceeded` with the honest minimum card kept), `retail_blurb.md`
  (editorial blurb from the top three quotes), `provenance.json` (per-quote source: review
  index, line range, sentence index, reviewer, rating, words dropped, all transformations,
  source sha256 prefix, `requires_human_verification: true`).
- **CLI** (`cli.py`): documented flags, sensible exit codes (0/1/2), stdin support (`-i -`).

The project is a companion to, and distinct from, `arc-review-tracker-webapp` (ARC pipeline
management) and `book-promo-graphics-template` (visual card design).

## How to run it

```bash
pip install -e .                # Python 3.10+, stdlib-only, offline
reviewquote -i examples/sample_reviews.txt -o /tmp/out --title "The Massive AI Manual"
# or without installing:
python3 -m review_quote_formatter -i reviews.txt -o out/
```

Help: `reviewquote --help` · Version: `reviewquote --version`

## Verification results

- `python3 -m pytest` → **39 passed** (parser, extraction/trimming, style, provenance,
  end-to-end CLI, stdin, exit codes, social-budget fitting)
- `python3 -m py_compile` on all package and test modules → OK
- `pip install -e .` → OK; `reviewquote --version` → `reviewquote 1.0.0`
- End-to-end run on `examples/sample_reviews.txt` produced all four output files; quotes,
  attributions, and provenance records checked manually (see README for outputs)
- Exit codes verified: missing file → 1, empty input → 1, no positive sentences → 2,
  success → 0; stdin path verified

## Known gaps

- Keyword-based sentiment scoring is a heuristic: it is tuned for positive marketing
  quotes and will miss unusual phrasings; a negative-context sentence that slips through
  is still fully logged for human verification, which is the intended workflow.
- Reviewer-line parsing is intentionally strict (dash prefix or known platform name); some
  pasted layouts will fall back to "verified reader" attribution.
- Trimmed quotes are marked `human_review_required`; no citations/links are generated to
  original URLs (the input format is pasted text only).
- Social cards are plain text, not images — pair with `book-promo-graphics-template` for
  visuals.
- No packaging beyond an editable-install console script; no CI configuration yet.
