"""Sidebar option builders for transcript/group selections."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import streamlit as st

from transcriptx.web.cache_helpers import (
    cached_list_available_sessions,
    cached_list_viewable_session_names,
)
from transcriptx.web.perf import mark_cache_miss


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


def _library_only_slugs_from_index(session_slugs: set[str]) -> list[str]:
    """Registered index slugs not already covered by a viewable run.

    Skips entries whose ``source_path`` is set but missing on disk.
    """
    from transcriptx.core.utils.slug_manager import list_all_transcripts

    extras: list[str] = []
    for entry in list_all_transcripts():
        slug = entry.get("slug")
        if not slug or slug in session_slugs:
            continue
        source_path = entry.get("source_path")
        if source_path:
            try:
                if not Path(source_path).expanduser().exists():
                    continue
            except OSError:
                continue
        extras.append(str(slug))
    return extras


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
    index_mtime: float | None,
) -> tuple[list[str], dict[str, str]]:
    """Assemble sorted dropdown options + slug labels (cached across reruns)."""
    mark_cache_miss("transcript_dropdown_options")
    slug_labels = _slug_display_labels_from_index()
    session_slugs = {name.split("/", 1)[0] for name in session_names if "/" in name}
    options: list[str] = list(session_slugs)
    options.extend(_library_only_slugs_from_index(session_slugs))
    options = list(dict.fromkeys(options))
    formatter = _make_option_formatter(slug_labels)
    options.sort(key=lambda value: (formatter(value).lower(), str(value)))
    return options, slug_labels


def clear_transcript_dropdown_caches() -> None:
    """Invalidate sidebar dropdown assembler cache (called from listing clears)."""
    _cached_dropdown_options.clear()  # type: ignore[attr-defined]


def get_transcript_dropdown_options() -> tuple[list[str], Callable[[str], str]]:
    """Return merged transcript options and formatter for selectbox."""
    session_names = tuple(cached_list_viewable_session_names())
    options, slug_labels = _cached_dropdown_options(session_names, _slug_index_mtime())
    return options, _make_option_formatter(slug_labels)
