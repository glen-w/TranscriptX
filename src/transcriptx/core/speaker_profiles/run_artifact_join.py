"""Shared helpers for Speakers-detail packs that join run artifacts to appearances.

Used by locations / interactions / sentiment packs. Derived, disposable — not
canonical store state. Prefer newest run under the session that contains the
requested artifact; soft-skip appearances without usable evidence.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from transcriptx.core.speaker_profiles.aggregates import AppearanceRow
from transcriptx.core.speaker_profiles.models import SpeakerProfileV1
from transcriptx.core.speaker_profiles.snapshot import AggregationSnapshot
from transcriptx.core.utils.paths import OUTPUTS_DIR, PATHS
from transcriptx.core.utils.slug_manager import load_index
from transcriptx.io.speaker_map_resolver import (
    SpeakerMapResolver,
    resolve_speaker_display_label,
)

__all__ = [
    "appearance_transcript_path",
    "load_json",
    "match_keys_for_appearance",
    "newest_run_with",
    "paths_match",
    "slug_for_transcript_path",
]


def paths_match(left: str | Path, right: str | Path) -> bool:
    try:
        left_path = Path(left).expanduser().resolve(strict=False)
        right_path = Path(right).expanduser().resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return str(left) == str(right)
    if left_path == right_path:
        return True
    try:
        if left_path.is_file() and right_path.is_file():
            return os.path.samefile(left_path, right_path)
    except (OSError, ValueError):
        pass
    return False


def slug_for_transcript_path(path: Path) -> str | None:
    normalized = str(path.expanduser().resolve(strict=False))
    try:
        index = load_index()
    except Exception:
        return None
    for entry in index.get("transcripts", {}).values():
        if not isinstance(entry, dict):
            continue
        source_path = entry.get("source_path", "")
        if not source_path:
            continue
        if paths_match(source_path, normalized):
            slug = entry.get("slug")
            return str(slug) if slug else None
    return None


def appearance_transcript_path(
    snap: AggregationSnapshot, row: AppearanceRow
) -> Path | None:
    bundle = snap.bundles.get(row.managed_transcript_id)
    if bundle is not None and bundle.resolved is not None:
        return Path(bundle.resolved.transcript_path)
    if row.current_relpath:
        return PATHS.transcripts_dir / row.current_relpath
    if row.observed_transcript_relpath:
        return PATHS.transcripts_dir / row.observed_transcript_relpath
    return None


def match_keys_for_appearance(
    *,
    profile: SpeakerProfileV1,
    local_speaker_key: str,
    transcript_path: Path,
) -> frozenset[str]:
    keys: set[str] = {local_speaker_key.casefold(), profile.display_name.casefold()}
    for alias in profile.aliases:
        alias_s = str(alias or "").strip()
        if alias_s:
            keys.add(alias_s.casefold())
    try:
        state = SpeakerMapResolver().load_mapping(transcript_path)
        mapped = resolve_speaker_display_label(local_speaker_key, state)
        if mapped:
            keys.add(mapped.casefold())
    except Exception:
        pass
    return frozenset(k for k in keys if k)


def load_json(path: Path) -> Any | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return data


def newest_run_with(
    session_slug: str,
    find_artifact: Callable[[Path], Path | None],
    *,
    outputs_dir: Path | None = None,
) -> tuple[str, Path] | None:
    """Return (run_id, artifact_path) for the newest run that has the artifact."""
    base = Path(outputs_dir if outputs_dir is not None else OUTPUTS_DIR) / session_slug
    if not base.is_dir():
        return None
    candidates: list[tuple[float, str, Path]] = []
    for run_dir in base.iterdir():
        if not run_dir.is_dir() or run_dir.name.startswith("."):
            continue
        artifact = find_artifact(run_dir)
        if artifact is None:
            continue
        try:
            mtime = float(run_dir.stat().st_mtime)
        except OSError:
            mtime = float("-inf")
        candidates.append((mtime, run_dir.name, artifact))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    _mtime, run_id, artifact = candidates[0]
    return run_id, artifact


def pick_speaker_entry(
    mapping: Mapping[str, Any] | None, match_keys: frozenset[str]
) -> tuple[str, Any] | None:
    """Return (original_key, value) for the first mapping key matching match_keys."""
    if not mapping:
        return None
    for key, value in mapping.items():
        if str(key).casefold() in match_keys:
            return str(key), value
    return None
