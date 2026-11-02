"""Cached session → transcript path resolution (no cache_helpers import cycle)."""

from __future__ import annotations

import streamlit as st

from transcriptx.web.perf import mark_cache_miss


@st.cache_data(ttl=60, show_spinner=False)
def _cached_resolve_transcript_path(
    session_name: str, outputs_dir: str, transcripts_dir: str
) -> str | None:
    """Cached session -> transcript path resolution (manifest reads + path probes)."""
    mark_cache_miss("cached_resolve_transcript_path")
    from transcriptx.web.services.file_service import FileService

    path = FileService.resolve_transcript_path(session_name)
    return str(path) if path is not None else None


def cached_resolve_transcript_path(session_name: str) -> str | None:
    """Resolve a session name to its transcript path via a short-lived cache.

    Callers must verify the returned path still exists (renames can leave the
    cache stale within the TTL) and fall back to a direct resolve when it doesn't.
    """
    from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR, OUTPUTS_DIR

    return _cached_resolve_transcript_path(
        session_name, str(OUTPUTS_DIR), str(DIARISED_TRANSCRIPTS_DIR)
    )
