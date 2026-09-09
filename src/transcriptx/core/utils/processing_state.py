"""Processing state helpers for TranscriptX.

``processing_state.json`` is a derived index for rename/audio-link/delete
bookkeeping. It is not run execution truth — consumers that need module
status must read ``run_results.json`` (see the run outcome contract).
New features should prefer the filesystem plus ``run_results.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import NAMESPACE_URL, uuid4, uuid5

from transcriptx.core.utils.file_lock import FileLock, cleanup_stale_locks
from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.paths import PROCESSING_STATE_FILE

logger = get_logger()


def _is_uuid_format(key: str) -> bool:
    parts = key.split("-")
    return len(parts) == 5 and all(parts)


def _normalize_path(value: str | Path) -> str:
    return str(Path(value).expanduser().resolve())


def _ensure_transcript_uuid(transcript_path: Optional[str]) -> str:
    if transcript_path:
        try:
            return str(uuid5(NAMESPACE_URL, _normalize_path(transcript_path)))
        except Exception:
            return str(uuid4())
    return str(uuid4())


def _load_state_file(state_file: Path) -> Dict[str, Any]:
    if not state_file.exists():
        return {"processed_files": {}}
    with open(state_file, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Processing state at {state_file} is not a JSON object")
    data.setdefault("processed_files", {})
    if not isinstance(data["processed_files"], dict):
        data["processed_files"] = {}
    return data


def load_processing_state(
    state_file: str | Path | None = None,
    validate: bool = True,
    *,
    skip_migration: bool = False,
) -> Dict[str, Any]:
    """Load processing state from disk with optional validation."""
    target_file = Path(state_file) if state_file else PROCESSING_STATE_FILE
    try:
        cleanup_stale_locks(target_file.with_suffix(".lock"))
        if not target_file.exists():
            return {"processed_files": {}}

        with FileLock(target_file, timeout=5, blocking=False) as lock:
            if not lock.acquired:
                logger.warning("State file is locked, using empty state")
                return {"processed_files": {}}

            state = _load_state_file(target_file)

            if validate:
                from transcriptx.core.utils.state_utils import (
                    repair_processing_state,
                    validate_processing_state,
                )

                validation_result = validate_processing_state(target_file)
                if not validation_result.get("valid", True):
                    logger.warning(
                        "State file validation found issues: %s",
                        validation_result.get("errors", []),
                    )
                    repair_result = repair_processing_state(backup=True, dry_run=False)
                    if repair_result.get("repaired"):
                        state = _load_state_file(target_file)

            if not skip_migration and validate:
                processed_files = state.get("processed_files", {})
                if processed_files and not all(
                    _is_uuid_format(key) for key in processed_files.keys()
                ):
                    migration_result = migrate_processing_state_to_uuid_keys()
                    if migration_result.get("migrated"):
                        state = _load_state_file(target_file)

            return state
    except json.JSONDecodeError as e:
        log_error("PROCESSING_STATE", f"State file is corrupted: {e}", exception=e)
        return {"processed_files": {}}
    except Exception as e:
        log_error(
            "PROCESSING_STATE", f"Error loading processing state: {e}", exception=e
        )
        return {"processed_files": {}}


def save_processing_state(
    state: Dict[str, Any], state_file: str | Path | None = None
) -> None:
    """Save processing state atomically."""
    target_file = Path(state_file) if state_file else PROCESSING_STATE_FILE
    target_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with FileLock(target_file, timeout=30) as lock:
            if not lock.acquired:
                raise RuntimeError("Could not acquire lock for state file")

            temp_file = target_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2, ensure_ascii=False)
            temp_file.replace(target_file)
    except Exception as e:
        log_error(
            "PROCESSING_STATE", f"Error saving processing state: {e}", exception=e
        )
        raise


def same_resolved_path(a: str | None, b: str | None) -> bool:
    """Return True if two path strings refer to the same file (after resolve)."""
    if not a or not b:
        return False
    try:
        return _normalize_path(a) == _normalize_path(b)
    except Exception:
        return str(a) == str(b)


def find_processed_entry_for_path(
    transcript_path: str,
    state: Optional[Dict[str, Any]] = None,
) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Return ``(state_key, entry)`` for the ``processed_files`` row that refers to
    this transcript, matching by resolved path equality.

    Compares against ``transcript_path``, ``current_transcript_path``,
    ``original_transcript_path``, and ``file_path`` so renames and strict vs
    unresolved string forms still match (fixes missed updates after rename).
    """
    try:
        normalized = _normalize_path(transcript_path)
    except Exception:
        normalized = str(Path(transcript_path).expanduser())
    current_state = (
        state if state is not None else load_processing_state(validate=False)
    )
    processed_files = current_state.get("processed_files", {}) or {}
    for key, entry in processed_files.items():
        if not isinstance(entry, dict):
            continue
        candidate_paths = [
            entry.get("transcript_path"),
            entry.get("current_transcript_path"),
            entry.get("original_transcript_path"),
            entry.get("file_path"),
        ]
        for p in candidate_paths:
            if not p:
                continue
            try:
                if _normalize_path(p) == normalized:
                    return key, entry
            except Exception:
                continue
    return None, None


def is_file_processed(file_path: Path, state: Optional[Dict[str, Any]] = None) -> bool:
    """Return True if a transcript path already exists in processing state."""
    normalized = _normalize_path(file_path)
    current_state = (
        state if state is not None else load_processing_state(validate=False)
    )
    processed_files = current_state.get("processed_files", {}) or {}
    for key, entry in processed_files.items():
        if key == normalized or key == _ensure_transcript_uuid(normalized):
            return True
        if not isinstance(entry, dict):
            continue
        candidate_paths = [
            entry.get("transcript_path"),
            entry.get("current_transcript_path"),
            entry.get("original_transcript_path"),
            entry.get("file_path"),
            entry.get("audio_path"),
        ]
        if any(
            path and _normalize_path(path) == normalized for path in candidate_paths
        ):
            return True
    return False


def mark_file_processed(file_path: Path, metadata: Dict[str, Any]) -> None:
    """Record a processed transcript in processing state."""
    normalized = _normalize_path(file_path)
    state = load_processing_state(validate=False)
    processed_files = state.setdefault("processed_files", {})
    key = _ensure_transcript_uuid(normalized)
    entry = dict(metadata or {})
    entry.setdefault("transcript_path", normalized)
    entry.setdefault("current_transcript_path", normalized)
    entry.setdefault("original_transcript_path", normalized)
    entry.setdefault("transcript_uuid", key)
    processed_files[key] = entry
    save_processing_state(state)


def migrate_processing_state_to_uuid_keys() -> Dict[str, Any]:
    """Normalize processing-state keys to UUIDs derived from transcript paths."""
    state = load_processing_state(validate=False, skip_migration=True)
    processed_files = state.get("processed_files", {}) or {}
    if not processed_files:
        return {"migrated": False, "reason": "no entries", "entries_migrated": 0}
    if all(_is_uuid_format(k) for k in processed_files.keys()):
        return {
            "migrated": False,
            "reason": "Already using UUID keys",
            "entries_migrated": 0,
        }

    migrated: Dict[str, Any] = {}
    entries_migrated = 0
    for key, entry in processed_files.items():
        if not isinstance(entry, dict):
            continue
        transcript_path = (
            entry.get("transcript_path")
            or entry.get("current_transcript_path")
            or entry.get("original_transcript_path")
            or key
        )
        uuid_key = _ensure_transcript_uuid(str(transcript_path))
        normalized_entry = dict(entry)
        normalized_entry.setdefault("transcript_path", _normalize_path(transcript_path))
        normalized_entry.setdefault(
            "current_transcript_path", normalized_entry["transcript_path"]
        )
        normalized_entry.setdefault(
            "original_transcript_path", normalized_entry["transcript_path"]
        )
        normalized_entry["transcript_uuid"] = uuid_key
        migrated[uuid_key] = normalized_entry
        entries_migrated += 1

    if not entries_migrated:
        return {"migrated": False, "reason": "no valid entries", "entries_migrated": 0}

    state["processed_files"] = migrated
    save_processing_state(state)
    return {
        "migrated": True,
        "entries_migrated": entries_migrated,
        "reason": "converted to UUID keys",
    }


def get_current_transcript_path_from_state(transcript_path: str) -> Optional[str]:
    """Return the current transcript path stored in processing state if present."""
    normalized = _normalize_path(transcript_path)
    state = load_processing_state(validate=False)
    processed_files = state.get("processed_files", {}) or {}
    for key, entry in processed_files.items():
        if key == normalized or key == _ensure_transcript_uuid(normalized):
            if isinstance(entry, dict):
                return (
                    entry.get("current_transcript_path")
                    or entry.get("transcript_path")
                    or entry.get("original_transcript_path")
                )
        if isinstance(entry, dict):
            for candidate in (
                entry.get("current_transcript_path"),
                entry.get("transcript_path"),
                entry.get("original_transcript_path"),
                entry.get("file_path"),
            ):
                if candidate and _normalize_path(candidate) == normalized:
                    return candidate
    return normalized if Path(normalized).exists() else None


def get_tags_for_path(
    path: str | Path,
    state: Optional[Dict[str, Any]] = None,
) -> list[str]:
    """Return sanitized library tags for a transcript path from processing state."""
    from transcriptx.io.tag_validation import sanitize_tag_list

    _, entry = find_processed_entry_for_path(str(path), state=state)
    if not isinstance(entry, dict):
        return []
    raw = entry.get("tags")
    if not isinstance(raw, list):
        return []
    return sanitize_tag_list([str(t) for t in raw if isinstance(t, str)])


def set_tags_for_path(
    path: str | Path,
    tags: list[str] | None,
    *,
    auto_tags: list[str] | None = None,
) -> list[str]:
    """Persist sanitized library tags (and tag_details) for a transcript path."""
    from transcriptx.io.tag_validation import build_tag_details, sanitize_tag_list

    normalized = _normalize_path(path)
    clean = sanitize_tag_list(list(tags or []))
    auto_clean = sanitize_tag_list(list(auto_tags or []))

    state = load_processing_state(validate=False)
    key, entry = find_processed_entry_for_path(normalized, state=state)
    existing = dict(entry) if isinstance(entry, dict) else {}
    existing_details = existing.get("tag_details")
    if not isinstance(existing_details, dict):
        existing_details = {}

    details = build_tag_details(clean, auto_clean, existing_details)
    existing["tags"] = clean
    existing["tag_details"] = details
    existing.setdefault("transcript_path", normalized)
    existing.setdefault("current_transcript_path", normalized)
    existing.setdefault("original_transcript_path", normalized)

    if key is None:
        mark_file_processed(Path(normalized), existing)
    else:
        processed_files = state.setdefault("processed_files", {})
        uuid_key = key if _is_uuid_format(key) else _ensure_transcript_uuid(normalized)
        existing.setdefault("transcript_uuid", uuid_key)
        if uuid_key != key and key in processed_files:
            del processed_files[key]
        processed_files[uuid_key] = existing
        save_processing_state(state)

    return clean


def list_entries_by_tags(
    required: list[str] | tuple[str, ...] | None,
    *,
    match: str = "all",
    state: Optional[Dict[str, Any]] = None,
) -> list[tuple[str, dict]]:
    """Return ``(state_key, entry)`` pairs whose tags match ``required``.

    ``match="all"`` requires every required tag; ``match="any"`` requires one.
    """
    from transcriptx.io.tag_validation import sanitize_tag_list

    needed = sanitize_tag_list(list(required or []))
    if not needed:
        return []
    if match not in {"all", "any"}:
        raise ValueError('match must be "all" or "any"')

    current_state = (
        state if state is not None else load_processing_state(validate=False)
    )
    processed_files = current_state.get("processed_files", {}) or {}
    needed_set = set(needed)
    matched: list[tuple[str, dict]] = []
    for key, entry in processed_files.items():
        if not isinstance(entry, dict):
            continue
        entry_tags = set(
            sanitize_tag_list(
                [str(t) for t in (entry.get("tags") or []) if isinstance(t, str)]
            )
        )
        if match == "all":
            if not needed_set.issubset(entry_tags):
                continue
        elif not needed_set.intersection(entry_tags):
            continue
        matched.append((key, entry))
    return matched
