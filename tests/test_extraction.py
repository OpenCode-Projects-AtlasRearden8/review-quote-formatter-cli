"""Tests for sentence extraction, scoring, and honest trimming."""

from review_quote_formatter.parser import ReviewBlock
from review_quote_formatter.extraction import (
    _honest_cut_points,
    extract_quotes,
    split_sentences,
    trim_quote,
)


def make_block(text: str, reviewer: str = "Jane D.", platform: str = "Amazon") -> ReviewBlock:
    return ReviewBlock(text=text, reviewer=reviewer, platform=platform)


def test_split_sentences_basic():
    sentences = split_sentences("I loved it. Dr. Smith said buy it! Also very clear.")
    assert sentences == ["I loved it.", "Dr. Smith said buy it!", "Also very clear."]


def test_positive_sentences_scored_and_sorted():
    block = make_block(
        "Terrible, confusing, skip it. The examples are practical and the tone is warm. I loved it."
    )
    quotes = extract_quotes([block], top=2, max_words=16)
    assert quotes
    assert all(q.score >= 1.5 for q in quotes)
    texts = {q.original for q in quotes}
    assert "The examples are practical and the tone is warm." in texts


def test_negated_keyword_disqualified():
    quotes = extract_quotes([make_block("I did not love this book.")], top=5)
    assert not quotes


def test_negative_words_disqualified():
    quotes = extract_quotes(
        [make_block("The tools were unpredictable, the flow confusing, but warm in tone.")]
    )
    assert not quotes


def test_max_per_review_enforced():
    block = make_block(
        "The examples are practical and the tone is warm. I loved it. Genuinely my favorite gift to any beginner."
    )
    quotes = extract_quotes([block], top=5, max_per_review=1)
    assert len(quotes) == 1


def test_overlong_untrimmable_candidates_skipped():
    filler = " ".join(["deep", "brilliant", "useful"] * 12)  # keyword-rich but no clause boundaries
    quotes = extract_quotes([make_block(filler)], top=5, max_words=16)
    assert not quotes


def test_trim_short_sentence_untouched():
    styled, transforms, dropped = trim_quote("I loved it.", 16)
    assert styled == "I loved it."
    assert dropped == 0
    assert transforms == []


def test_trim_at_comma_boundary_with_ellipsis():
    long_sentence = (
        "The troubleshooting tips alone are worth the price, and the free AI coding"
        " chapter paid for the book ten times over."
    )
    styled, transforms, dropped = trim_quote(long_sentence, 16)
    assert styled.startswith("The troubleshooting tips alone are worth the price")
    assert styled.endswith("…")
    assert not styled.startswith(" ") and "  " not in styled
    assert "trailing_ellipsis_added" in transforms
    assert dropped == len(long_sentence.split()) - len(styled.replace("…", "").split())
    assert "human_review_required" in transforms


def test_trailing_comma_stripped_before_ellipsis():
    long_sentence = "This book is a gift, and the final chapters are worth every single penny of its price."
    styled, transforms, _ = trim_quote(long_sentence, 6)
    assert styled == "This book is a gift…"
    assert not styled.endswith(",…")


def test_trim_keeps_terminal_punctuation_without_ellipsis():
    sentence = "Every chapter is useful. It just drags in the middle, sadly, and then it ends abruptly."
    styled, transforms, dropped = trim_quote(sentence, 6)
    assert styled == "Every chapter is useful."
    assert "trailing_ellipsis_added" not in transforms
    assert dropped == len(sentence.split()) - 4
    assert "terminal_punctuation_kept" in transforms


def test_no_dangling_negation():
    sentence = "I would not recommend this to beginners, but experts will love it for the depth."
    styled, transforms, dropped = trim_quote(sentence, 10)
    # the only comma cut is preceded by "recommend" (fine) but ends the kept
    # text on "beginners" — allowed only if it does not end on a negation;
    # the negation "not" is not at a clause boundary so kept text never
    # ends on it.
    assert "not…" not in styled
    assert not styled.rstrip("…").lower().endswith(" not")


def test_untrimmable_sentence_returned_whole():
    sentence = " ".join(f"word{i}" for i in range(30))
    styled, transforms, dropped = trim_quote(sentence, 16)
    assert styled == sentence
    assert dropped == 0
    assert transforms == []


def test_no_cut_inside_second_contrast_clause():
    sentence = "This book is rich, but the ending is brilliant, practical, and warm throughout the guide."
    words = sentence.split()
    but_index = words.index("but,") if "but," in words else words.index("but")
    for k in _honest_cut_points(words):
        assert k < but_index, "no cut may open inside the but-clause"


def test_cut_directly_before_contrast_refused():
    words = "The tone is warm, gentle, helpful, but the pace drags in chapter nine a bit.".split()
    cuts = _honest_cut_points(words)
    for k in cuts:
        assert words[k + 1].strip(",.!?").lower() != "but"
    # earlier clausal cuts stay positive and legitimate
    assert words[max(cuts)].startswith("gentle")


def test_cuts_swallowing_a_but_clause_are_refused():
    words = "The basics are excellent, but part two is superb, and depth seems clear to me, truly.".split()
    but_index = words.index("but,") if "but," in words else words.index("but")
    for k in _honest_cut_points(words):
        assert k < but_index or words[k].strip().endswith((".", "!", "?")), k
