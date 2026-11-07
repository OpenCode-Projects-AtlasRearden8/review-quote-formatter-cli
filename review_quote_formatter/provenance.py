"""Provenance logging for every extracted quote.

Each quote gets a record tying it back to the exact source review: which
input (sha256 prefix), which review block (line range), which sentence,
what was dropped, and every house-style transformation applied. Nothing
here is meant to replace human judgment - the log exists so a human CAN
verify that no quote misrepresents its source.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .extraction import Quote


def input_sha256(raw: str, length: int = 12) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def build_record(quote: Quote, hash_prefix: str) -> dict:
    return {
        "quote": quote.text,
        "original_sentence": quote.original,
        "reviewer": quote.source.reviewer,
        "platform": quote.source.platform,
        "rating": quote.source.rating,
        "source_review_index": quote.source_review_index,
        "source_line_start": quote.source.start_line + 1,
        "source_line_end": quote.source.end_line + 1,
        "sentence_index": quote.sentence_index,
        "words_dropped": quote.dropped_words,
        "transformations": list(quote.transformations),
        "source_sha256_prefix": hash_prefix,
        "requires_human_verification": True,
    }


def write_provenance(records: list[dict], hash_prefix: str, path: Path) -> Path:
    payload = {
        "hash_prefix": hash_prefix,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notice": "Every quote must be verified by a human against its source review before use.",
        "quotes": records,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
