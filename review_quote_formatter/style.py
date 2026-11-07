"""House style enforcement: caps rules and ellipsis rules.

Caps rules
    * Words shouted in ALL CAPS (4+ letters, alphabetic) are softened to
      Title Case so quotes read professionally; known acronyms are kept.
      Every change is logged as a ``downcased_shouting`` transformation -
      subscribers to the honesty rule can diff against the source.
    * If a quote starts with a lowercase letter, a bracketed capital is
      inserted (``[A]bsolutely loved it``) - the universal editorial
      convention that leaves the original untouched and visible.

Ellipsis rules
    * One glyph (``…``; ``...`` with ``--ascii-ellipsis``), no space
      before, no space after.
    * Nothing is ever quoted that begins with an ellipsis.
    * Omitted trailing words are either marked with the ellipsis or,
      when the kept text already ends on sentence punctuation, shown
      as-is (the terminal mark makes the omission unambiguous).

Quotes are wrapped in straight double quotes in all outputs so text is
copy-paste safe everywhere.
"""

from __future__ import annotations

import re

ACRONYM_WHITELIST = {
    "AI", "ARC", "ISBN", "KDP", "USA", "FAQ", "PDF", "EPUB", "HTML", "LLM", "GPT", "MCP", "TLDR", "POV", "NLP",
}

_WORD_TOKEN_RE = re.compile(r"[A-Za-z]+(?:['][A-Za-z]+)?")
_SHOUTING_RE = re.compile(r"^[A-Z]{4,}$")
_ELL_RUN_RE = re.compile(r"…|\.\.\.+|(?:\.\s*){2,}")


def _title_case(word: str) -> str:
    return word[:1] + word[1:].lower()


def caps_pass(text: str) -> tuple[str, list[str]]:
    """Soften SHOUTING words, keep whitelisted acronyms. Returns (text, changes)."""
    changes: list[str] = []

    def repl(match: re.Match[str]) -> str:
        word = match.group(0)
        if _SHOUTING_RE.match(word) and word not in ACRONYM_WHITELIST:
            softened = _title_case(word)
            changes.append(f"downcased_shouting:{word}->{softened}")
            return softened
        return word

    return _WORD_TOKEN_RE.sub(repl, text), changes


def bracketed_initial_cap(text: str) -> tuple[str, list[str]]:
    """Insert a bracketed capital when a quote starts lowercase."""
    stripped = text.lstrip("“”\"' ")
    if stripped and stripped[0].islower():
        marker = "@CAP@"
        head, sep, tail = text.partition(stripped[0])
        rebuilt = f"{head}[{stripped[0].upper()}]{stripped[1:]}"
        return rebuilt.replace(marker, ""), [f"bracketed_initial_cap:[{stripped[0]}]"]
    return text, []


def normalize_ellipsis(text: str, ascii_ellipsis: bool = False) -> tuple[str, list[str]]:
    """Canonicalize ellipsis; remove leading ellipsis. Returns (text, changes)."""
    glyph = "..." if ascii_ellipsis else "…"
    marker = "@ELL@"
    changes: list[str] = []
    found = False

    def repl(match: re.Match[str]) -> str:
        nonlocal found
        found = True
        return marker

    tagged = _ELL_RUN_RE.sub(repl, text)
    if not found:
        return text, changes
    stripped = tagged.lstrip()
    if stripped.startswith(marker):
        tagged = stripped[len(marker):].lstrip()
        changes.append("removed_leading_ellipsis:POLICY")
    tagged = re.sub(r"(?:@ELL@[ ]?)+", "@ELL@", tagged)
    rebuilt = tagged.replace(marker, glyph)
    rebuilt = re.sub(r"[ \t]{2,}", " ", rebuilt).strip()
    if rebuilt != text:
        changes.append("ellipsis_normalized")
    return rebuilt, changes


def wrap_quotes(text: str) -> str:
    """Straight double quotes around a quote."""
    return f'"{text}"'
