"""Stable occurrence keys for Corrections Studio (segment + span + wrong text)."""

from __future__ import annotations

import hashlib


def stable_occurrence_key(
    segment_id: str, span_start: int, span_end: int, wrong_text: str
) -> str:
    """SHA-1 hex digest of ``segment_id:span_start:span_end:wrong_text`` (UTF-8)."""
    sig = f"{segment_id}:{span_start}:{span_end}:{wrong_text}"
    return hashlib.sha1(sig.encode("utf-8")).hexdigest()
