"""Tests for review text parsing."""

from review_quote_formatter.parser import ReviewBlock, parse_reviews

DASHED = """Great book, loved it.
-- Jordan P., Amazon

---

-- Dee W., Goodreads
Every chapter earns its place."""

STAR_LINE = """★★★★★ Clear and practical
The examples helped so much.
— Priya K., NetGalley"""

NOPARSE = """just a wall of text with no metadata
and a second line"""


def test_divider_blocks():
    blocks = parse_reviews(DASHED)
    assert len(blocks) == 2
    assert blocks[0].reviewer == "Jordan P." and blocks[0].platform == "Amazon review"
    assert blocks[0].text.strip().startswith("Great book")
    assert blocks[1].reviewer == "Dee W." and blocks[1].platform == "Goodreads review"
    assert "Every chapter earns its place." in blocks[1].text


def test_star_rating_and_reviewer_line():
    blocks = parse_reviews(STAR_LINE)
    assert len(blocks) == 1
    assert blocks[0].rating == "★★★★★"
    assert blocks[0].reviewer == "Priya K."
    assert blocks[0].platform == "NetGalley review"
    assert "The examples helped so much." in blocks[0].text


def test_no_metadata_block_is_body_only():
    blocks = parse_reviews(NOPARSE)
    assert len(blocks) == 1
    assert blocks[0].reviewer is None
    assert blocks[0].reviewer_label == "verified reader"


def test_blank_blocks_skipped():
    blocks = parse_reviews("----\n----\n body \n")
    assert len(blocks) == 1


def test_line_numbers_recorded():
    raw = "line zero\n-- Jane D., Amazon\nbody text\n"
    blocks = parse_reviews(raw)
    assert blocks[0].start_line == 0 and blocks[0].end_line == len(raw.strip().splitlines()) - 1


def test_reviewer_label_variants():
    b = ReviewBlock(text="x", reviewer=None, platform="Amazon")
    assert b.reviewer_label == "Amazon"
    b2 = ReviewBlock(text="x", reviewer=None, platform=None)
    assert b2.reviewer_label == "verified reader"
