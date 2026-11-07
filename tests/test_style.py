"""Tests for house-style caps and ellipsis rules."""

from review_quote_formatter.style import (
    bracketed_initial_cap,
    caps_pass,
    normalize_ellipsis,
    wrap_quotes,
)


def test_shouting_softened_and_logged():
    text, changes = caps_pass("This book was AMAZING and endlessly USEFUL.")
    assert text == "This book was Amazing and endlessly Useful."
    assert "downcased_shouting:AMAZING->Amazing" in changes
    assert "downcased_shouting:USEFUL->Useful" in changes


def test_acronyms_preserved():
    text, changes = caps_pass("Great for AI beginners who use KDP and MCP tools.")
    assert text == "Great for AI beginners who use KDP and MCP tools."
    assert changes == []


def test_bracketed_initial_cap():
    text, changes = bracketed_initial_cap("absolutely loved it.")
    assert text == "[A]bsolutely loved it."
    assert changes == ["bracketed_initial_cap:[a]"]


def test_bracketed_cap_untouched_when_capitalized():
    text, changes = bracketed_initial_cap("Loved it.")
    assert text == "Loved it." and changes == []


def test_ellipsis_normalization_glyph():
    text, changes = normalize_ellipsis("I loved the depth . . . honestly, the clarity.")
    assert "…" in text
    assert " ." not in text
    assert "ellipsis_normalized" in changes


def test_no_leading_ellipsis():
    text, changes = normalize_ellipsis("… and the tone is warm.")
    assert not text.startswith("…")
    assert "removed_leading_ellipsis:POLICY" in changes


def test_ascii_ellipsis_flag():
    text, _ = normalize_ellipsis("so good…", ascii_ellipsis=True)
    assert text.endswith("...")
    assert "…" not in text


def test_wrap_quotes():
    assert wrap_quotes("Nice.") == '"Nice."'
