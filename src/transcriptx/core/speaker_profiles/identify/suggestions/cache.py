"""Cache assistive name suggestions per managed transcript."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from transcriptx.core.speaker_profiles.identify.suggestions.models import (
    NameSuggestionsResult,
)
from transcriptx.core.speaker_profiles.layout import speaker_profiles_dir
from transcriptx.io.atomic_json import write_json_atomic


def suggestions_cache_path(
    managed_transcript_id: str, *, root: Path | None = None
) -> Path:
    base = Path(root) if root is not None else speaker_profiles_dir()
    return (
        base
        / ".cache"
        / "identify"
        / f"{managed_transcript_id}.name_suggestions.v1.json"
    )


def load_suggestions_artefact(
    managed_transcript_id: str, *, root: Path | None = None
) -> NameSuggestionsResult | None:
    path = suggestions_cache_path(managed_transcript_id, root=root)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return NameSuggestionsResult.from_dict(raw)


def load_cached_suggestions(
    managed_transcript_id: str,
    *,
    transcript_fingerprint: str,
    root: Path | None = None,
) -> NameSuggestionsResult | None:
    path = suggestions_cache_path(managed_transcript_id, root=root)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    if raw.get("transcript_fingerprint") != transcript_fingerprint:
        return None
    return NameSuggestionsResult.from_dict(raw)


def write_cached_suggestions(
    result: NameSuggestionsResult,
    *,
    root: Path | None = None,
) -> Path | None:
    if not result.managed_transcript_id:
        return None
    path = suggestions_cache_path(result.managed_transcript_id, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = result.to_dict()
    write_json_atomic(path, payload, indent=2)
    return path
