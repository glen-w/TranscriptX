"""Map vendor speaker ids onto WhisperX ``SPEAKER_XX`` labels."""

from __future__ import annotations

import re
from typing import Any

_SPEAKER_NUM_RE = re.compile(r"(\d+)")


def speaker_label(raw: Any, *, one_based: bool = False) -> str | None:
    """Normalize a speaker id to WhisperX ``SPEAKER_XX``.

    ``one_based=True`` maps IBM/Granite 1-based numbers (1 → SPEAKER_00).
    ``one_based=False`` keeps Nemotron 0-based numbers (0 → SPEAKER_00).
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.upper().startswith("SPEAKER_"):
        return text
    match = _SPEAKER_NUM_RE.search(text)
    if match is None:
        return text
    number = int(match.group(1))
    if one_based:
        index = number - 1 if number >= 1 else number
    else:
        index = number
    if index < 0:
        index = 0
    return f"SPEAKER_{index:02d}"
