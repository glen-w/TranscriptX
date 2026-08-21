"""Permanently dismissed Auto-merge suggestions.

Persisted under ``CONFIG_DIR/audio_merge_dismissed.json``. Keys match
``SerialGroup.dismissal_key`` (rule + stem). Session **Hide** does not write
here; **Don't suggest again** does, so later visits and
``whispermlx-missing --skip-serial`` treat the files as separate recordings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from transcriptx.core.utils.paths import CONFIG_DIR
from transcriptx.io.atomic_json import locked_path, write_bytes_atomic

SCHEMA_VERSION = 1
DISMISSED_FILENAME = "audio_merge_dismissed.json"


def dismissed_path(config_dir: Path | None = None) -> Path:
    root = Path(config_dir) if config_dir is not None else Path(CONFIG_DIR)
    return root / DISMISSED_FILENAME


def _normalize_keys(keys: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in keys:
        key = str(raw).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _keys_from_payload(payload: Any) -> list[str]:
    if isinstance(payload, list):
        return _normalize_keys(str(item) for item in payload)
    if not isinstance(payload, dict):
        return []
    raw_keys = payload.get("keys", [])
    if not isinstance(raw_keys, list):
        return []
    return _normalize_keys(str(item) for item in raw_keys)


def _read_keys_unlocked(target: Path) -> list[str]:
    if not target.is_file():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    return _keys_from_payload(payload)


def _write_keys_unlocked(target: Path, keys: Iterable[str]) -> None:
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "keys": _normalize_keys(keys),
    }
    payload = (json.dumps(envelope, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    write_bytes_atomic(target, payload)


def load_permanently_dismissed_keys(
    *,
    config_dir: Path | None = None,
    path: Path | None = None,
) -> list[str]:
    """Load dismissed keys. Missing or invalid file → empty list."""
    target = path if path is not None else dismissed_path(config_dir)
    return _read_keys_unlocked(target)


def save_permanently_dismissed_keys(
    keys: Iterable[str],
    *,
    config_dir: Path | None = None,
    path: Path | None = None,
) -> Path:
    """Atomically write dismissed keys."""
    target = path if path is not None else dismissed_path(config_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    with locked_path(target):
        _write_keys_unlocked(target, keys)
    return target


def add_permanently_dismissed_key(
    key: str,
    *,
    config_dir: Path | None = None,
    path: Path | None = None,
) -> list[str]:
    """Append *key* if missing; return the stored list."""
    target = path if path is not None else dismissed_path(config_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    with locked_path(target):
        keys = _read_keys_unlocked(target)
        normalized = str(key).strip()
        if normalized and normalized not in keys:
            keys.append(normalized)
        _write_keys_unlocked(target, keys)
        return list(keys)


def remove_permanently_dismissed_key(
    key: str,
    *,
    config_dir: Path | None = None,
    path: Path | None = None,
) -> list[str]:
    """Drop *key* if present; return the stored list."""
    target = path if path is not None else dismissed_path(config_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    with locked_path(target):
        keys = [
            item for item in _read_keys_unlocked(target) if item != str(key).strip()
        ]
        _write_keys_unlocked(target, keys)
        return list(keys)


def serial_group_dismissal_key(group: Any) -> str:
    """``SerialGroup.dismissal_key``, or rule:stem for lite group objects."""
    key = getattr(group, "dismissal_key", None)
    if key:
        return str(key)
    return f"{getattr(group, 'matched_rule', '')}:{getattr(group, 'base_key', '')}"


def filter_permanently_dismissed(
    groups: Iterable[Any],
    *,
    config_dir: Path | None = None,
    path: Path | None = None,
    dismissed_keys: Iterable[str] | None = None,
) -> list[Any]:
    """Drop groups whose dismissal key is permanently stored."""
    if dismissed_keys is None:
        dismissed = set(
            load_permanently_dismissed_keys(config_dir=config_dir, path=path)
        )
    else:
        dismissed = set(_normalize_keys(dismissed_keys))
    if not dismissed:
        return list(groups)
    return [
        group for group in groups if serial_group_dismissal_key(group) not in dismissed
    ]
