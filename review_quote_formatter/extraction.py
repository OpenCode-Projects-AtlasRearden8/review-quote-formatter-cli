"""Extract pull-quote candidates from review blocks and trim them honestly.

Wholesale honesty rules for trimming:

1. A quote may never *start* with an ellipsis; it starts on real text.
2. A kept prefix may never end on a negation word (``not``, ``never``,
   ``no``, ``without`` ...) - ending on negation can flip the meaning.
3. A cut may not orphan a contrast: if dropping a tail would leave the
   kept part hanging off a contrast word (``but``, ``however`` ...), the
   cut is refused and the full sentence is used (if it fits) or skipped.
4. Anything dropped is recorded in the provenance log so a human can
   verify the quote against the source review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .parser import ReviewBlock

NEGATION_WORDS = {"not", "never", "no", "nothing", "without", "cannot", "hardly", "isn't", "wasn't", "don't", "didn't", "won't", "wouldn't", "can't"}
CONTRAST_WORDS = {"but", "however", "although", "though", "except", "unless", "whereas", "yet"}
POSITIVE_KEYWORDS = [
    "must-read",
    "must read",
    "love",
    "loved",
    "brilliant",
    "excellent",
    "essential",
    "refreshing",
    "recommend",
    "amazing",
    "fantastic",
    "wonderful",
    "stellar",
    "outstanding",
    "clear",
    "clearly",
    "helpful",
    "practical",
    "useful",
    "insightful",
    "thorough",
    "engaging",
    "page-turner",
    "unputdownable",
    "best",
    "great",
    "smart",
    "warm",
    "gift",
    "superb",
    "accessible",
    "perfect",
    "solid",
    "top-notch",
    "gem",
    "impressed",
    "impressive",
    "treasure",
    "valuable",
    "clear-eyed",
    "clarity",
    "plain",
    "worth",
    "gripping",
    "riveting",
    "masterclass",
    "definitive",
    "standout",
    "extraordinary",
]

ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "prof", "st", "vs", "etc", "e.g", "i.e", "jr", "sr"}


@dataclass
class Quote:
    text: str
    source: ReviewBlock
    source_review_index: int
    sentence_index: int
    original: str
    score: float = 0.0
    transformations: list[str] = field(default_factory=list)
    dropped_words: int = 0
    attribution_override: str | None = None

    def attribution(self) -> str:
        return self.attribution_override or self.attribution_label()

    def attribution_label(self) -> str:
        return self.source.reviewer_label


def _inflected(token: str, keyword: str) -> bool:
    """True when ``token`` is a plain inflection of ``keyword`` (loves/loved/clears)."""
    if not token.startswith(keyword):
        return False
    suffix = token[len(keyword):]
    return suffix == "" or suffix in {"s", "es", "ed", "ed,", "d", "ing", "ful"} or (keyword.endswith("e") and suffix in {"d", "ed"})


def split_sentences(text: str) -> list[str]:
    """Split text into sentences, tolerant of common abbreviations.

    Paragraph breaks count as sentence boundaries.
    """
    guarded = re.sub(
        r"\b(" + "|".join(ABBREVIATIONS) + r")\.",
        lambda m: m.group(1).replace(".", "\x00") + "\x00",
        text,
        flags=re.IGNORECASE,
    )
    guarded = re.sub(r"\s*\n\s*", "\x01", guarded)
    parts = [
        p.replace("\x00", ".").replace("\x01", " ").strip()
        for p in re.split(r"(?<=[.!?])\s+|\x01", guarded)
    ]
    return [p for p in parts if p]


def _score_sentence(sentence: str) -> float | None:
    """Score a sentence as a pull-quote candidate; None = disqualified."""
    words = sentence.split()
    if len(words) < 3 or len(words) > 60:
        return None
    low = " " + sentence.lower() + " "
    score = 0.0
    hits = 0
    tokens = [w.strip(".,!?;:\"'“”‘’()").lower() for w in words]
    for i, token in enumerate(tokens):
        for keyword in POSITIVE_KEYWORDS:
            if token == keyword or _inflected(token, keyword):
                hits += 1
                score += 2
                if i > 0 and tokens[i - 1] in NEGATION_WORDS:
                    return None
                break
    if hits == 0:
        return None
    if any(token in CONTRAST_WORDS for token in tokens):
        score -= 1.5
    if any(neg in tokens for neg in ("mediocre", "disappoint", "boring", "confusing", "shallow", "fluffy", "error", "inaccurate", "skip")):
        return None
    if 6 <= len(words) <= 22:
        score += 1
    return score


def extract_quotes(blocks: list[ReviewBlock], top: int = 5, max_per_review: int = 2, min_score: float = 1.5, max_words: int | None = None) -> list[Quote]:
    """Best pull-quote candidate sentences across all review blocks.

    When ``max_words`` is given, candidates that are too long to trim
    honestly at that budget (no clause-boundary cut point available) are
    skipped so no over-length quote is ever emitted.
    """
    candidates: list[Quote] = []
    for index, block in enumerate(blocks):
        sentences = split_sentences(block.text)
        seen = set()
        for j, sentence in enumerate(sentences):
            score = _score_sentence(sentence)
            if score is None or score < min_score:
                continue
            if max_words is not None and not _usable_at_budget(sentence, max_words):
                continue
            fingerprint = " ".join(sentence.lower().split()[:8])
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            candidates.append(
                Quote(
                    text=sentence,
                    source=block,
                    source_review_index=index,
                    sentence_index=j,
                    original=sentence,
                    score=score,
                )
            )
    candidates.sort(key=lambda q: (-q.score, q.source_review_index, q.sentence_index))
    picked: list[Quote] = []
    per_review: dict[int, int] = {}
    for candidate in candidates:
        if len(picked) >= top:
            break
        if per_review.get(candidate.source_review_index, 0) >= max_per_review:
            continue
        per_review[candidate.source_review_index] = per_review.get(candidate.source_review_index, 0) + 1
        picked.append(candidate)
    picked.sort(key=lambda q: (q.source_review_index, q.sentence_index))
    return picked


def _usable_at_budget(sentence: str, max_words: int) -> bool:
    """A sentence is usable if it fits, or trims honestly at the budget."""
    words = sentence.split()
    if len(words) <= max_words:
        return True
    return any(k + 1 <= max_words for k in _honest_cut_points(words))


def _honest_cut_points(words: list[str]) -> list[int]:
    """Indices k so that keeping words[: k + 1] does not twist the sentence.

    Cuts are only allowed at clause boundaries: right after a word ending
    in comma or terminal punctuation. Three guards apply:
      * a kept region may never end on a negation or contrast word;
      * if the kept region contains a negation or contrast word, the cut
        must end on terminal punctuation (a complete statement);
      * a cut directly before a contrast word is refused, so the quote
        never silently hides a "but"-clause it used to stand next to.
    """
    strip_chars = ".,!?;:\"'“”‘’()"
    lowered = [w.strip(strip_chars).lower() for w in words]
    tricky = lambda w: w in NEGATION_WORDS or w in CONTRAST_WORDS
    points: list[int] = []
    for k in range(len(words) - 1):
        token = words[k].strip()
        if not token or token[-1] not in ".,!?":
            continue
        bare = token.strip(strip_chars).lower()
        if tricky(bare):
            continue
        next_bare = lowered[k + 1] if k + 1 < len(words) else ""
        if next_bare in CONTRAST_WORDS:
            continue
        kept_tricky = any(tricky(w) for w in lowered[: k + 1])
        ends_terminal = token[-1] in ".!?"
        if kept_tricky and not ends_terminal:
            continue
        points.append(k)
    return points


def trim_quote(sentence: str, max_words: int, ascii_ellipsis: bool = False) -> tuple[str, list[str], int]:
    """Return (styled_quote_text, transformations, dropped_word_count)."""
    ellipsis = "..." if ascii_ellipsis else "…"
    words = sentence.split()
    transformations: list[str] = []
    dropped = 0
    if len(words) <= max_words:
        styled = sentence
    else:
        cuts = [k for k in _honest_cut_points(words) if k + 1 <= max_words]
        if not cuts:
            return sentence, transformations, 0
        k = max(cuts)
        kept = words[: k + 1]
        dropped = len(words) - len(kept)
        last = kept[-1].strip()
        if last and last[-1] in ".!?":
            styled = " ".join(kept)
            transformations.append("dropped_trailing_words")
            transformations.append("terminal_punctuation_kept")
        else:
            if last.endswith(","):
                kept[-1] = last[:-1]
            styled = " ".join(kept).rstrip(",") + ellipsis
            transformations.append("trailing_ellipsis_added")
            transformations.append("dropped_trailing_words")
        transformations.append(f"trimmed:{dropped}")
        transformations.append("human_review_required")
    return styled, transformations, dropped
