"""Sidebar option builders for transcript/group selections."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from transcriptx.web.cache_helpers import cached_list_available_sessions
from transcriptx.web.services import FileService


def _build_session_index_from_list(sessions: list) -> dict:
    """Build slug -> [sessions] map from session list (no I/O)."""
    session_map = {}
    for session in sessions:
        name = session.get("name", "")
        if "/" not in name:
            continue
        slug, run_id = name.split("/", 1)
        session_map.setdefault(slug, [])
        session = {**session, "run_id": run_id}
        session_map[slug].append(session)
    return session_map


def get_cached_session_data():
    """Return (session_map, sessions_list) backed by cached_list_available_sessions."""
    sessions_list = cached_list_available_sessions()
    session_map = _build_session_index_from_list(sessions_list)
    return session_map, sessions_list


def _session_list_covers_transcript_path(
    sessions_list: list, transcript_path: Path
) -> bool:
    """True if some session resolves to the same file on disk (including samefile)."""
    try:
        target = transcript_path.expanduser().resolve()
    except (OSError, RuntimeError):
        return False
    for session in sessions_list:
        name = session.get("name", "")
        if "/" not in name:
            continue
        resolved = FileService.resolve_transcript_path(name)
        if resolved is None:
            continue
        try:
            rp = resolved.resolve()
        except (OSError, RuntimeError):
            continue
        if rp == target:
            return True
        try:
            if os.path.samefile(rp, target):
                return True
        except (OSError, ValueError):
            continue
    return False


def _slug_display_labels_from_index() -> dict[str, str]:
    """Map output folder slug -> friendly basename."""
    from transcriptx.core.utils.slug_manager import load_index

    labels: dict[str, str] = {}
    for _tk, entry in load_index().get("transcripts", {}).items():
        slug = entry.get("slug")
        basename = entry.get("source_basename")
        if slug and basename:
            labels[slug] = basename
    return labels


def get_transcript_dropdown_options() -> tuple[list[str], Callable[[str], str]]:
    """Return merged transcript options and formatter for selectbox."""
    session_map, sessions_list = get_cached_session_data()
    session_slugs = set(session_map.keys())
    slug_labels = _slug_display_labels_from_index()
    try:
        from transcriptx.web.cache_helpers import get_cached_list_transcripts

        raw = get_cached_list_transcripts()
    except Exception:
        raw = []

    options: list[str] = []
    options.extend(session_slugs)
    for transcript in raw:
        try:
            tp = Path(transcript.path).expanduser().resolve()
        except (OSError, RuntimeError):
            continue
        if not _session_list_covers_transcript_path(sessions_list, tp):
            options.append(str(tp))

    def _format(opt: str) -> str:
        p = Path(opt)
        if p.is_absolute() and p.suffix.lower() == ".json":
            return p.stem
        return slug_labels.get(opt, opt)

    options.sort(key=lambda value: (_format(value).lower(), str(value)))
    return options, _format
