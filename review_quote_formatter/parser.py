"""Parse pasted review text into ReviewBlock objects.

Accepted input shapes (per block, blocks separated by divider lines or by
separating blank lines):

    Review text paragraph one...
    second paragraph...
    -- Marcus T., Amazon

or

    -- Jane D., Goodreads
    Loved every chapter.

Divider lines of 3+ dashes/equals/asterisks always start a new block.
Single blank lines separate paragraphs *within* a block; a review with no
divider and no blank lines is treated as one block.

No names, emails, or handles are required; anything not matching the
reviewer-line pattern is left as review body text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_DIVIDER_RE = re.compile(r"^\s*(?:-{3,}|={3,}|\*{3,}|_{3,})\s*$")
# e.g. "-- Marcus T., Amazon" / "— Jane D., Goodreads" / "Jane D. | Amazon"
REVIEWER_LINE_RE = re.compile(
    r"^\s*(?:[-–—]{1,2}\s*)?(?P<who>[A-Za-z][A-Za-z .'-]{1,38}?)\s*(?:,|\||\bon\b)\s*"
    r"(?P<where>[A-Za-z][A-Za-z &'-]{1,30})\s*$"
)
STARS_RE = re.compile(r"^\s*[★☆⭐✱]*\s*(?:\d(?:\.\d)?\s*/\s*5\s*stars?)?\s*[★☆⭐✱]*\s*$")
LEADING_STARS_RE = re.compile(r"^(?P<stars>[★☆⭐✱]{3,}|\d(?:\.\d)?\s*/\s*5\s*stars?)\s*(?P<rest>.*)$")

PLATFORMS = {
    "amazon": "Amazon review",
    "goodreads": "Goodreads review",
    "netgalley": "NetGalley review",
    "storygraph": "StoryGraph review",
    "the storygraph": "StoryGraph review",
    "kobo": "Kobo review",
    "barnes & noble": "Barnes & Noble review",
    "b&n": "Barnes & Noble review",
    "apple books": "Apple Books review",
    "bookbub": "BookBub review",
    "library journal": "Library Journal review",
    "kirkus": "Kirkus review",
    "publishers weekly": "Publishers Weekly review",
    "booklist": "Booklist review",
}


@dataclass
class ReviewBlock:
    text: str
    reviewer: str | None
    platform: str | None
    rating: str | None = None
    start_line: int = 0
    end_line: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def reviewer_label(self) -> str:
        if self.reviewer and self.platform:
            return f"{self.reviewer}, {self.platform}"
        return self.reviewer or self.platform or "verified reader"


def _classify_line(line: str) -> tuple[str | None, str | None, str | None]:
    """Return (reviewer, platform, rating) if the line is metadata."""
    stripped = line.strip()
    if STARS_RE.match(stripped):
        return None, None, stripped or "5 stars"
    m = REVIEWER_LINE_RE.match(stripped)
    if m:
        who, where = m.group("who").strip(), m.group("where").strip()
        known_platform = where.lower() in PLATFORMS
        prefixed = bool(re.match(r"^\s*[-–—]", stripped))
        if who and where and who.lower() not in {"a", "the"} and (known_platform or prefixed):
            platform = PLATFORMS.get(where.lower(), where)
            return who, platform, None
    return None, None, None


def parse_reviews(raw: str) -> list[ReviewBlock]:
    """Parse raw pasted review text into review blocks."""
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[ReviewBlock] = []
    current: list[tuple[int, str]] = []

    def flush(entries: list[tuple[int, str]]) -> None:
        if not entries:
            return
        reviewer = platform = rating = None
        body: list[str] = []
        for lineno, line in entries:
            stripped = line.strip()
            if not stripped:
                body.append("")
                continue
            candidate_reviewer, candidate_platform, candidate_rating = _classify_line(stripped)
            if candidate_rating and reviewer is None:
                rating = candidate_rating
                continue
            if candidate_reviewer and reviewer is None:
                reviewer, platform = candidate_reviewer, candidate_platform
                continue
            star_lead = LEADING_STARS_RE.match(stripped)
            if star_lead:
                if rating is None:
                    rating = star_lead.group("stars")
                rest = star_lead.group("rest").strip()
                if rest:
                    body.append(rest)
                    body.append("")
                continue
            body.append(line)
        text = _clean_body(body)
        if not text and not rating:
            return
        blocks.append(
            ReviewBlock(
                text=text,
                reviewer=reviewer,
                platform=platform,
                rating=rating,
                start_line=entries[0][0],
                end_line=entries[-1][0],
            )
        )

    divider_positions = [i for i, line in enumerate(lines) if _DIVIDER_RE.match(line)]
    if divider_positions:
        start = 0
        for pos in divider_positions + [len(lines)]:
            current = [(i, lines[i]) for i in range(start, pos) if lines[i].strip()]
            flush(current)
            start = pos + 1
    else:
        flush([(i, line) for i, line in enumerate(lines) if line.strip()])
    return blocks


def _clean_body(body: list[str]) -> str:
    paragraphs: list[str] = []
    current: list[str] = []
    for entry in body:
        if entry == "":
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(entry.strip())
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs).strip()
