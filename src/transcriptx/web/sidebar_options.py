"""Sidebar option builders for transcript/group selections."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import streamlit as st

from transcriptx.web.cache_helpers import cached_list_available_sessions
from transcriptx.web.perf import mark_cache_miss
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


def _session_names(sessions_list: list) -> tuple[str, ...]:
    """Stable cache key: session names with a slug/run_id shape."""
    return tuple(
        sorted(
            session.get("name", "")
            for session in sessions_list
            if "/" in session.get("name", "")
        )
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_session_path_index(
    session_names: tuple[str, ...],
) -> tuple[set[str], set[tuple[int, int]]]:
    """Resolve each session's transcript once; return resolved paths + (dev, ino) keys."""
    mark_cache_miss("session_path_index")
    paths: set[str] = set()
    inode_keys: set[tuple[int, int]] = set()
    for name in session_names:
        resolved = FileService.resolve_transcript_path(name)
        if resolved is None:
            continue
        try:
            rp = resolved.resolve()
        except (OSError, RuntimeError):
            continue
        paths.add(str(rp))
        try:
            file_stat = rp.stat()
        except OSError:
            continue
        inode_keys.add((file_stat.st_dev, file_stat.st_ino))
    return paths, inode_keys


def _path_covered(
    target: Path, paths: set[str], inode_keys: set[tuple[int, int]]
) -> bool:
    """Membership check against precomputed session path index (incl. samefile)."""
    if str(target) in paths:
        return True
    try:
        file_stat = target.stat()
    except OSError:
        return False
    return (file_stat.st_dev, file_stat.st_ino) in inode_keys


def _session_list_covers_transcript_path(
    sessions_list: list, transcript_path: Path
) -> bool:
    """True if some session resolves to the same file on disk (including samefile)."""
    try:
        target = transcript_path.expanduser().resolve()
    except (OSError, RuntimeError):
        return False
    paths, inode_keys = _cached_session_path_index(_session_names(sessions_list))
    return _path_covered(target, paths, inode_keys)


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


def _slug_index_mtime() -> float | None:
    """Slug index file mtime; used as a cache key so label caches stay fresh."""
    from transcriptx.core.utils.slug_manager import INDEX_FILE

    try:
        return INDEX_FILE.stat().st_mtime
    except OSError:
        return None


def _make_option_formatter(slug_labels: dict[str, str]) -> Callable[[str], str]:
    def _format(opt: str) -> str:
        p = Path(opt)
        if p.is_absolute() and p.suffix.lower() == ".json":
            return p.stem
        return slug_labels.get(opt, opt)

    return _format


@st.cache_data(ttl=60, show_spinner=False)
def _cached_dropdown_options(
    session_names: tuple[str, ...],
    library_paths: tuple[str, ...],
    index_mtime: float | None,
) -> tuple[list[str], dict[str, str]]:
    """Assemble sorted dropdown options + slug labels (cached across reruns)."""
    mark_cache_miss("transcript_dropdown_options")
    slug_labels = _slug_display_labels_from_index()
    paths, inode_keys = _cached_session_path_index(session_names)

    options: list[str] = sorted({name.split("/", 1)[0] for name in session_names})
    for path_str in library_paths:
        try:
            tp = Path(path_str).expanduser().resolve()
        except (OSError, RuntimeError):
            continue
        if not _path_covered(tp, paths, inode_keys):
            options.append(str(tp))

    formatter = _make_option_formatter(slug_labels)
    options.sort(key=lambda value: (formatter(value).lower(), str(value)))
    return options, slug_labels


def get_transcript_dropdown_options() -> tuple[list[str], Callable[[str], str]]:
    """Return merged transcript options and formatter for selectbox."""
    _session_map, sessions_list = get_cached_session_data()
    try:
        from transcriptx.web.cache_helpers import get_cached_list_transcripts

        raw = get_cached_list_transcripts()
    except Exception:
        raw = []

    library_paths = tuple(str(t.path) for t in raw)
    options, slug_labels = _cached_dropdown_options(
        _session_names(sessions_list), library_paths, _slug_index_mtime()
    )
    return options, _make_option_formatter(slug_labels)
