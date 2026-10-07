"""Natural-language transcript title detection and underscore formatting."""

from __future__ import annotations

import re
from typing import Literal

from transcriptx.core.utils.rename.audio_association import looks_like_uuid
from transcriptx.core.utils.rename.smart_name import (
    parse_recording_datetime_from_stem,
    parse_voice_note_stem,
)

_TOKEN_SPLIT = re.compile(r"[\s_\-]+")
_CAMEL_PART = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")
_STOPWORDS = frozenset({"a", "an", "the", "of", "and", "or", "in", "on", "for", "to"})


def split_title_tokens(stem: str) -> list[str]:
    """Split a stem into title words (spaces, underscores, CamelCase)."""
    raw = (stem or "").strip()
    if not raw:
        return []
    out: list[str] = []
    for chunk in _TOKEN_SPLIT.split(raw):
        if not chunk:
            continue
        parts = _CAMEL_PART.findall(chunk)
        if parts:
            out.extend(parts)
        else:
            out.append(chunk)
    return out


def underscore_title(stem: str) -> str:
    """Join title tokens with underscores."""
    tokens = split_title_tokens(stem)
    if not tokens:
        return ""
    return "_".join(tokens)


def is_generic_device_filename_stem(stem: str) -> bool:
    """True when the stem looks like a device/recording filename, not a human title."""
    s = (stem or "").strip()
    if not s:
        return True
    if parse_recording_datetime_from_stem(s) is not None:
        return True
    if parse_voice_note_stem(s) is not None:
        return True
    if looks_like_uuid(s):
        return True
    if re.fullmatch(r"\d+", s):
        return True
    return False


def stem_looks_like_natural_language_title(stem: str) -> bool:
    """True when the stem is likely a descriptive title rather than a device name."""
    s = (stem or "").strip()
    if is_generic_device_filename_stem(s):
        return False
    if len(s) < 8:
        return False
    if not re.search(r"[A-Za-z]", s):
        return False
    if re.search(r"[\s_\-]", s):
        return True
    if re.search(r"[a-z][A-Z]", s):
        return True
    if re.search(r"[A-Z]", s) and len(s) >= 12:
        return True
    return False


def propose_dated_title(date_root: str, stem: str) -> str:
    """``YYMMDD_`` prefix plus underscored title; avoid doubling an existing date prefix."""
    dr = (date_root or "").strip()
    if dr and not dr.endswith("_"):
        dr = f"{dr}_"
    titled = underscore_title(stem)
    if not titled:
        return dr
    yymmdd = dr.rstrip("_")
    if yymmdd and (stem.startswith(f"{yymmdd}_") or stem == yymmdd):
        return titled
    if yymmdd and titled.startswith(f"{yymmdd}_"):
        return titled
    return f"{dr}{titled}" if dr else titled


def title_word_bubbles(stem: str, *, max_tokens: int = 8) -> tuple[str, ...]:
    """Clickable title tokens (stopwords dropped)."""
    words = [w for w in split_title_tokens(stem) if w.lower() not in _STOPWORDS]
    return tuple(words[:max_tokens])


BubbleTokenCase = Literal["title", "upper", "lower"]


def format_bubble_token(token: str, case: BubbleTokenCase) -> str:
    """Apply display/append casing to a rename token bubble."""
    piece = (token or "").strip()
    if not piece:
        return piece
    if case == "upper":
        return piece.upper()
    if case == "lower":
        return piece.lower()
    return "_".join(part.capitalize() for part in piece.split("_"))


def format_rename_stem_case(stem: str, case: BubbleTokenCase) -> str:
    """Apply casing to each underscore-separated segment of a rename target stem."""
    raw = (stem or "").strip()
    if not raw:
        return raw
    parts = raw.split("_")
    return "_".join(format_bubble_token(part, case) for part in parts if part)
