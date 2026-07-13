"""Validated theme/content phrase resources (not merged into global tic mask)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from transcriptx.core.utils.config import THEME_PHRASE_RESOURCES_FILE
from transcriptx.core.utils.notifications import notify_user

_REQUIRED_LIST_KEYS = (
    "discourse_formulas",
    "light_verbs",
    "pronoun_subjects",
    "discourse_nouns",
)

_NORMALIZE_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_phrase_text(text: str) -> str:
    """Case-fold, strip punctuation, collapse whitespace."""
    lowered = (text or "").casefold().strip()
    cleaned = _NORMALIZE_RE.sub(" ", lowered)
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def tokenize_normalized(text: str) -> tuple[str, ...]:
    normalized = normalize_phrase_text(text)
    if not normalized:
        return ()
    return tuple(tok for tok in normalized.split(" ") if tok)


@dataclass(frozen=True)
class ThemePhraseResources:
    discourse_formulas: frozenset[tuple[str, ...]]
    light_verbs: frozenset[str]
    pronoun_subjects: frozenset[str]
    discourse_nouns: frozenset[str]
    fingerprint: str


_resources_cache: ThemePhraseResources | None = None


def _as_string_list(value: Any, *, key: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"theme phrase resource '{key}' must be a list")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"theme phrase resource '{key}' entries must be strings")
        out.append(item)
    return out


def _dedupe_normalized_phrases(phrases: Iterable[str]) -> list[tuple[str, ...]]:
    seen: set[tuple[str, ...]] = set()
    ordered: list[tuple[str, ...]] = []
    for phrase in phrases:
        tokens = tokenize_normalized(phrase)
        if not tokens or tokens in seen:
            continue
        seen.add(tokens)
        ordered.append(tokens)
    ordered.sort()
    return ordered


def _dedupe_normalized_tokens(tokens: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for token in tokens:
        norm = normalize_phrase_text(token)
        if not norm or " " in norm or norm in seen:
            continue
        seen.add(norm)
        ordered.append(norm)
    ordered.sort()
    return ordered


def validate_theme_phrase_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalise a theme phrase resources payload."""
    if not isinstance(payload, dict):
        raise ValueError("theme phrase resources payload must be an object")
    missing = [key for key in _REQUIRED_LIST_KEYS if key not in payload]
    if missing:
        raise ValueError(
            f"theme phrase resources missing required categories: {', '.join(missing)}"
        )
    formulas = _dedupe_normalized_phrases(
        _as_string_list(payload.get("discourse_formulas"), key="discourse_formulas")
    )
    light_verbs = _dedupe_normalized_tokens(
        _as_string_list(payload.get("light_verbs"), key="light_verbs")
    )
    pronoun_subjects = _dedupe_normalized_tokens(
        _as_string_list(payload.get("pronoun_subjects"), key="pronoun_subjects")
    )
    discourse_nouns = _dedupe_normalized_tokens(
        _as_string_list(payload.get("discourse_nouns"), key="discourse_nouns")
    )
    return {
        "discourse_formulas": formulas,
        "light_verbs": light_verbs,
        "pronoun_subjects": pronoun_subjects,
        "discourse_nouns": discourse_nouns,
    }


def _fingerprint_from_normalized(normalized: dict[str, Any]) -> str:
    material = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def load_theme_phrase_resources(
    path: Path | None = None,
    *,
    force_reload: bool = False,
) -> ThemePhraseResources:
    """Load theme phrase resources. Does not enlarge the global tic mask."""
    global _resources_cache
    if _resources_cache is not None and not force_reload and path is None:
        return _resources_cache

    resource_path = path or THEME_PHRASE_RESOURCES_FILE
    if not resource_path.exists():
        notify_user(
            f"Theme phrase resources file not found: {resource_path}",
            technical=True,
            section="ner",
        )
        empty = ThemePhraseResources(
            discourse_formulas=frozenset(),
            light_verbs=frozenset(),
            pronoun_subjects=frozenset(),
            discourse_nouns=frozenset(),
            fingerprint="missing",
        )
        if path is None:
            _resources_cache = empty
        return empty

    with open(resource_path, encoding="utf-8") as handle:
        payload = json.load(handle)
    try:
        normalized = validate_theme_phrase_payload(payload)
    except ValueError:
        # Fail closed for malformed resources at runtime: empty sets + warn.
        notify_user(
            f"Invalid theme phrase resources at {resource_path}; ignoring.",
            technical=True,
            section="ner",
        )
        empty = ThemePhraseResources(
            discourse_formulas=frozenset(),
            light_verbs=frozenset(),
            pronoun_subjects=frozenset(),
            discourse_nouns=frozenset(),
            fingerprint="invalid",
        )
        if path is None:
            _resources_cache = empty
        return empty

    resources = ThemePhraseResources(
        discourse_formulas=frozenset(
            tuple(t) for t in normalized["discourse_formulas"]
        ),
        light_verbs=frozenset(normalized["light_verbs"]),
        pronoun_subjects=frozenset(normalized["pronoun_subjects"]),
        discourse_nouns=frozenset(normalized["discourse_nouns"]),
        fingerprint=_fingerprint_from_normalized(normalized),
    )
    if path is None:
        _resources_cache = resources
    return resources


def resource_fingerprint(resources: ThemePhraseResources | None = None) -> str:
    return (resources or load_theme_phrase_resources()).fingerprint


def reset_theme_phrase_resources_cache() -> None:
    global _resources_cache
    _resources_cache = None
