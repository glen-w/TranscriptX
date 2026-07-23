"""Speaker accent colours: palette, hex normalize, unused assignment."""

from __future__ import annotations

import re
import secrets
from collections.abc import Iterable

from transcriptx.core.speaker_profiles.errors import SpeakerProfileContractError

# Distinct accents readable on dark and light themes (GUI auto-hash + create pool).
SPEAKER_ACCENTS: tuple[str, ...] = (
    "#5B8DEF",  # blue
    "#E07A5F",  # coral
    "#81B29A",  # sage
    "#F2CC8F",  # gold
    "#9B8BB8",  # lavender
    "#7EB8DA",  # sky
)

_HEX6 = re.compile(r"^#[0-9A-F]{6}$")
_HEX3 = re.compile(r"^#[0-9A-Fa-f]{3}$")
_HEX6_ANY = re.compile(r"^#[0-9A-Fa-f]{6}$")
_RANDOM_RETRIES = 32


def normalize_accent_color(value: str) -> str:
    """Normalize to uppercase ``#RRGGBB``; reject alpha, named, rgb(), garbage."""
    raw = str(value or "").strip()
    if not raw:
        raise SpeakerProfileContractError("accent_color must be non-empty #RRGGBB")
    if raw.startswith("rgb") or raw.startswith("hsl") or " " in raw:
        raise SpeakerProfileContractError(
            f"accent_color must be #RRGGBB hex, got {value!r}"
        )
    if not raw.startswith("#"):
        raw = f"#{raw}"
    if _HEX3.fullmatch(raw):
        digits = raw[1:]
        raw = "#" + "".join(ch * 2 for ch in digits)
    if not _HEX6_ANY.fullmatch(raw):
        raise SpeakerProfileContractError(
            f"accent_color must be #RRGGBB hex, got {value!r}"
        )
    return raw.upper()


def is_safe_accent_css(value: str) -> bool:
    """True when ``value`` is safe to inject into ``--speaker-accent``."""
    try:
        return bool(_HEX6.fullmatch(normalize_accent_color(value)))
    except SpeakerProfileContractError:
        return False


def collect_used_accents(colors: Iterable[str | None]) -> set[str]:
    used: set[str] = set()
    for color in colors:
        if not color:
            continue
        try:
            used.add(normalize_accent_color(color))
        except SpeakerProfileContractError:
            continue
    return used


def assign_unused_accent(used: Iterable[str | None]) -> str:
    """Pick an unused palette colour at random, else a random freeform hex."""
    used_set = collect_used_accents(used)
    available = [c for c in SPEAKER_ACCENTS if c not in used_set]
    if available:
        return available[secrets.randbelow(len(available))]
    for _ in range(_RANDOM_RETRIES):
        candidate = f"#{secrets.token_hex(3).upper()}"
        if candidate not in used_set:
            return candidate
    return f"#{secrets.token_hex(3).upper()}"
