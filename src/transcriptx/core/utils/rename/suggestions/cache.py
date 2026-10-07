"""Cache assistive rename suggestions per transcript fingerprint."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from transcriptx.core.utils.paths import DATA_DIR
from transcriptx.core.utils.rename.suggestions.models import RenameSuggestionsResult
from transcriptx.io.atomic_json import write_json_atomic


def _cache_root() -> Path:
    return DATA_DIR / ".cache" / "rename"


def cache_path_for_key(cache_key: str) -> Path:
    digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:32]
    return _cache_root() / f"{digest}.rename_suggestions.v1.json"


def load_cached_rename_suggestions(
    *,
    cache_key: str,
    transcript_fingerprint: str,
) -> RenameSuggestionsResult | None:
    path = cache_path_for_key(cache_key)
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
    if raw.get("cache_key") != cache_key:
        return None
    return RenameSuggestionsResult.from_dict(raw)


def write_cached_rename_suggestions(result: RenameSuggestionsResult) -> Path | None:
    if not result.cache_key:
        return None
    path = cache_path_for_key(result.cache_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, result.to_dict(), indent=2)
    return path
