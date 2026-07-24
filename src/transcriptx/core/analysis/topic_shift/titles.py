"""Helpers for topic-shift chapter titles (viewer + enrichment)."""

from __future__ import annotations

import re

_GENERIC_TITLE_RE = re.compile(
    r"^\s*(segment|chapter)\s*\d+\b",
    re.IGNORECASE,
)


def is_usable_chapter_title(title: object, *, span_label: str | None = None) -> bool:
    """Reject empty / Segment-N echo titles so viewers can fall back to keywords."""
    text = str(title or "").strip()
    if not text:
        return False
    if _GENERIC_TITLE_RE.match(text):
        return False
    label = str(span_label or "").strip()
    if label and text.casefold() == label.casefold():
        return False
    if label and text.casefold().startswith(label.casefold()):
        return False
    return True
