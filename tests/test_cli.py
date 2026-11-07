"""End-to-end CLI tests: sample review text through the full pipeline."""

import json
from pathlib import Path

from review_quote_formatter.cli import main

SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "sample_reviews.txt"


def test_full_run_prod_outputs(tmp_path: Path):
    rc = main(
        [
            "-i", str(SAMPLE),
            "-o", str(tmp_path),
            "--title", "The Massive AI Manual",
        ]
    )
    assert rc == 0

    sheet = (tmp_path / "quote_sheet.md").read_text(encoding="utf-8")
    assert "# Pull Quotes — The Massive AI Manual" in sheet
    assert "—" in sheet  # attributions
    assert "Provenance" in sheet

    blurb = (tmp_path / "retail_blurb.md").read_text(encoding="utf-8")
    assert "The Massive AI Manual" in blurb
    assert "Asdale Dynamics, LLC" in blurb

    cards = sorted((tmp_path / "social").glob("card-*.txt"))
    assert cards
    for card in cards:
        body = card.read_text(encoding="utf-8")
        assert body.startswith('"')
        assert "—" in body
        assert len(body) <= 280

    provenance = json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))
    assert "verified" in provenance["notice"].lower()
    records = provenance["quotes"]
    assert len(records) == len(cards)
    for record in records:
        assert set(record) >= {
            "quote", "original_sentence", "source_review_index", "source_line_start",
            "source_line_end", "words_dropped", "transformations", "source_sha256_prefix",
            "requires_human_verification",
        }
        assert record["source_line_start"] >= 1


def test_no_positive_quotes_exit_code(tmp_path: Path):
    bad_input = tmp_path / "bad.txt"
    bad_input.write_text("This was dull and boring, sadly.\n-- Pat M., Amazon\n", encoding="utf-8")
    rc = main(["-i", str(bad_input), "-o", str(tmp_path / "out")])
    assert rc == 2


def test_missing_input_exit_code(tmp_path: Path):
    rc = main(["-i", str(tmp_path / "nope.txt"), "-o", str(tmp_path / "out")])
    assert rc == 1


def test_empty_input_exit_code(tmp_path: Path, capsys):
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    rc = main(["-i", str(empty), "-o", str(tmp_path / "out")])
    assert rc == 1
    assert "error" in capsys.readouterr().err


def test_ascii_ellipsis_flag(tmp_path: Path):
    rc = main(
        ["-i", str(SAMPLE), "-o", str(tmp_path), "--ascii-ellipsis", "--social-limit", "60"]
    )
    assert rc == 0
    text = "\n".join(p.read_text(encoding="utf-8") for p in (tmp_path / "social").glob("card-*.txt"))
    assert "…" not in text


def test_tight_social_budget_still_fits(tmp_path: Path):
    # limit 80: most quotes shorten honestly into the budget; when a quote
    # cannot go lower without twisting it, the closest fit is kept and the
    # compromise is logged in provenance as social_limit_exceeded.
    rc = main(["-i", str(SAMPLE), "-o", str(tmp_path), "--social-limit", "80"])
    assert rc == 0
    records = json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))["quotes"]
    over = {r["quote"] for r in records if "social_limit_exceeded" in r["transformations"]}
    for card in (tmp_path / "social").glob("card-*.txt"):
        body = card.read_text(encoding="utf-8")
        if any(part in body for part in over):
            continue
        assert len(body) <= 80, body


def test_untrimmable_respected_at_tiny_budget(tmp_path: Path):
    # max-words 3: an 8-word sentence with no clause boundary cannot be
    # trimmed honestly, so it is skipped entirely rather than misquoted.
    input_path = tmp_path / "in.txt"
    input_path.write_text(
        "This short refresher guide is absolutely brilliant overall.\n-- Robin Q., Amazon\n",
        encoding="utf-8",
    )
    rc = main(["-i", str(input_path), "-o", str(tmp_path / "out"), "--max-words", "3"])
    assert rc == 2
    assert not (tmp_path / "out" / "quote_sheet.md").exists()

    # a clause-boundary sentence trims honestly at the tiny budget
    input_path.write_text(
        "Warm book, honestly brilliant in tone, and clear throughout, cheers.\n-- Robin Q., Amazon\n",
        encoding="utf-8",
    )
    rc = main(["-i", str(input_path), "-o", str(tmp_path / "out2"), "--max-words", "3"])
    assert rc == 0
    record = json.loads((tmp_path / "out2" / "provenance.json").read_text(encoding="utf-8"))["quotes"][0]
    assert record["words_dropped"] > 0
    assert record["quote"] == "Warm book…"


def test_tiny_social_limit_logs_compromise(tmp_path: Path):
    input_path = tmp_path / "in.txt"
    input_path.write_text(
        "This friendly manual is absolutely brilliant for beginners, and deeply clear.\n-- Robin Q., Amazon\n",
        encoding="utf-8",
    )
    rc = main(["-i", str(input_path), "-o", str(tmp_path / "out"), "--social-limit", "30"])
    assert rc == 0
    provenance = json.loads((tmp_path / "out" / "provenance.json").read_text(encoding="utf-8"))
    record = provenance["quotes"][0]
    assert "social_limit_exceeded" in record["transformations"]
    # the compromise never invents words: the emitted card is the honest minimum
    card = next((tmp_path / "out" / "social").glob("card-*.txt")).read_text(encoding="utf-8")
    assert card.startswith('"') and "…" in card
