"""Provenance record tests."""

from review_quote_formatter.extraction import extract_quotes
from review_quote_formatter.parser import parse_reviews
from review_quote_formatter.provenance import build_record, input_sha256

RAW = """★★★★★ Warm and clear
The examples are practical and the tone is warm.
-- Jordan P., Amazon
"""


def test_hash_is_deterministic_prefix():
    h1 = input_sha256(RAW)
    h2 = input_sha256(RAW)
    assert h1 == h2 and len(h1) == 12


def test_build_record_shape():
    blocks = parse_reviews(RAW)
    quotes = extract_quotes(blocks, top=1)
    assert quotes
    record = build_record(quotes[0], input_sha256(RAW))
    assert record["reviewer"] == "Jordan P."
    assert record["source_line_start"] == 1
    assert record["requires_human_verification"] is True
    assert isinstance(record["transformations"], list)
