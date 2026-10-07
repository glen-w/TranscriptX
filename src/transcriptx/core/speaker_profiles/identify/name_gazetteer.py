"""Lazy given/surname gazetteer for speaker-name plausibility."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence

_PKG = Path(__file__).resolve().parents[3] / "preprocessing" / "names"

_GIVEN_OVERRIDE: frozenset[str] | None = None
_SURNAME_OVERRIDE: frozenset[str] | None = None


def set_gazetteer_for_tests(
    *,
    given: Iterable[str] | None = None,
    surnames: Iterable[str] | None = None,
) -> None:
    """Replace loaded sets (tests). Pass None to restore files."""
    global _GIVEN_OVERRIDE, _SURNAME_OVERRIDE
    _GIVEN_OVERRIDE = (
        None if given is None else frozenset(t.casefold() for t in given if t)
    )
    _SURNAME_OVERRIDE = (
        None if surnames is None else frozenset(t.casefold() for t in surnames if t)
    )
    given_tokens.cache_clear()
    surname_tokens.cache_clear()


def _load_list(path: Path) -> frozenset[str]:
    if not path.is_file():
        return frozenset()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return frozenset()
    if not isinstance(raw, list):
        return frozenset()
    return frozenset(str(item).strip().casefold() for item in raw if str(item).strip())


@lru_cache(maxsize=1)
def given_tokens() -> frozenset[str]:
    if _GIVEN_OVERRIDE is not None:
        return _GIVEN_OVERRIDE
    return _load_list(_PKG / "given_names.json")


@lru_cache(maxsize=1)
def surname_tokens() -> frozenset[str]:
    if _SURNAME_OVERRIDE is not None:
        return _SURNAME_OVERRIDE
    return _load_list(_PKG / "surnames.json")


def token_in_given(token: str) -> bool:
    return token.casefold() in given_tokens()


def token_in_surname(token: str) -> bool:
    return token.casefold() in surname_tokens()


def gazetteer_covers(tokens: Sequence[str]) -> bool:
    """True when tokens look like given, or given + surname."""
    parts = [t for t in tokens if t]
    if not parts:
        return False
    if len(parts) == 1:
        key = parts[0].casefold()
        return key in given_tokens() or key in surname_tokens()
    first_ok = parts[0].casefold() in given_tokens()
    last_ok = parts[-1].casefold() in surname_tokens()
    return first_ok and last_ok
