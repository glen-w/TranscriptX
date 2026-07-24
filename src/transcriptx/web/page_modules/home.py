"""
Home / Dashboard page for TranscriptX.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from transcriptx.utils.text_utils import (
    format_bytes_display,
    format_duration_display_from_config,
)
from transcriptx.web.cache_helpers import (
    cached_list_recent_runs,
    get_cached_count_managed_transcripts,
)
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.components.recent_run_row import render_recent_run_row
from transcriptx.web.perf import instrument_cached_call, set_count
from transcriptx.web.sidebar_options import _slug_display_labels_from_index
from transcriptx.web.utils import (
    get_all_sessions_statistics,
    list_available_sessions,
)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_sessions_and_stats() -> tuple[list, dict]:
    sessions = list_available_sessions()
    stats = dict(get_all_sessions_statistics())
    stats["library_transcript_count"] = get_cached_count_managed_transcripts()
    return sessions, stats


def _render_transcript_overview() -> bool:
    """Render library + analysed-transcript metrics. Returns True when sessions exist."""
    sessions, stats = _cached_sessions_and_stats()
    library_count = int(stats.get("library_transcript_count", 0))
    analysed_count = int(
        stats.get("total_transcripts", stats.get("total_sessions", 0) or 0)
    )
    if not sessions and library_count == 0:
        st.info("No transcripts found. Add transcripts in Library to get started.")
        return False

    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)
    with col1:
        st.metric(
            "Transcripts",
            library_count,
            help="Managed transcripts in Library",
        )
    with col2:
        st.metric(
            "Analysed transcripts",
            analysed_count,
            help="Unique transcripts with at least one viewable analysis run",
        )
    with col3:
        st.metric("Sessions", stats.get("total_sessions", len(sessions)))
    with col4:
        st.metric(
            "Total duration",
            format_duration_display_from_config(stats.get("total_duration_seconds", 0)),
            help="Sum of unique analysed transcript durations",
        )
    with col5:
        st.metric("Total words", f"{stats.get('total_word_count', 0):,}")
    with col6:
        st.metric("Speakers (max)", stats.get("total_speakers", 0))
    with col7:
        st.metric(
            "Analysis completion",
            f"{stats.get('average_completion', 0):.0f}%",
            help="Average analysis completion across analysed transcripts",
        )
    with col8:
        st.metric(
            "Size on disk",
            format_bytes_display(stats.get("total_artifact_bytes", 0)),
            help="Total size of produced analysis artifacts across all runs",
        )
    return bool(sessions)


def _render_sessions_table() -> None:
    """Render the per-session table in a collapsible section."""
    sessions, _stats = _cached_sessions_and_stats()
    if not sessions:
        return

    with st.expander("Sessions", expanded=False):
        rows = []
        for s in sorted(
            sessions,
            key=lambda session: session.get("duration_seconds", 0),
            reverse=True,
        ):
            rows.append(
                {
                    "Session": s.get("name", ""),
                    "Duration": format_duration_display_from_config(
                        s.get("duration_seconds", 0)
                    ),
                    "Words": s.get("word_count", 0),
                    "Segments": s.get("segment_count", 0),
                    "Speakers": s.get("speaker_count", 0),
                    "Completion %": s.get("analysis_completion", 0),
                }
            )
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def render_home() -> None:
    """Render the home/dashboard page."""
    render_page_shell("Home")

    try:
        if _render_transcript_overview():
            _render_sessions_table()

        runs = instrument_cached_call(
            "cached_list_recent_runs",
            cached_list_recent_runs,
            limit=10,
            bucket="home_summary",
        )
        set_count("recent_runs_returned", len(runs))

        with st.expander("Recent runs", expanded=False):
            if not runs:
                render_empty_state(
                    "no_results_yet",
                    "No analysis runs yet",
                    "Start from the Library or Run Analysis after adding transcripts.",
                    primary_action=("Run Analysis", "Run Analysis"),
                    secondary_action=("Library", "Library"),
                )
            else:
                slug_labels = _slug_display_labels_from_index()
                for idx, run in enumerate(runs[:5]):
                    render_recent_run_row(run, row_index=idx, slug_labels=slug_labels)
    except Exception as e:
        st.error(f"Could not load dashboard: {e}")
