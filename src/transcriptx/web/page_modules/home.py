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
    get_cached_home_light_summary,
)
from transcriptx.web.components.info_tooltip import widget_help
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.components.recent_run_row import render_recent_run_row
from transcriptx.web.perf import instrument_cached_call, set_count
from transcriptx.web.sidebar_options import _slug_display_labels_from_index
from transcriptx.web.utils import (
    get_all_sessions_statistics,
    list_available_sessions,
)

_HOME_DETAIL_STATS_KEY = "home_show_detailed_statistics"
_HOME_SESSIONS_KEY = "home_show_sessions"
_HOME_RECENT_RUNS_KEY = "home_show_recent_runs"


@st.cache_data(ttl=60, show_spinner=False)
def _cached_sessions_and_stats() -> tuple[list, dict]:
    sessions = list_available_sessions()
    stats = dict(get_all_sessions_statistics())
    return sessions, stats


def _render_transcript_overview() -> bool:
    """Render light count metrics. Returns True when library or sessions exist."""
    summary = get_cached_home_light_summary()
    library_count = int(summary.get("library_transcript_count", 0) or 0)
    analysed_count = int(summary.get("analysed_transcript_count", 0) or 0)
    session_count = int(summary.get("session_count", 0) or 0)
    if not summary.get("has_any"):
        st.info("No transcripts found. Add transcripts in Library to get started.")
        return False

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Transcripts",
            library_count,
            help=widget_help("Registered transcripts in the library index"),
        )
    with col2:
        st.metric(
            "Analysed transcripts",
            analysed_count,
            help=widget_help("Unique transcripts with at least one viewable analysis run"),
        )
    with col3:
        st.metric("Sessions", session_count)
    return True


def _render_detailed_statistics() -> None:
    """Rich aggregate metrics (opt-in; parses transcripts / manifests)."""
    _sessions, stats = _cached_sessions_and_stats()
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric(
            "Total duration",
            format_duration_display_from_config(stats.get("total_duration_seconds", 0)),
            help=widget_help("Sum of unique analysed transcript durations"),
        )
    with col2:
        st.metric("Total words", f"{stats.get('total_word_count', 0):,}")
    with col3:
        st.metric("Speakers (max)", stats.get("total_speakers", 0))
    with col4:
        st.metric(
            "Analysis completion",
            f"{stats.get('average_completion', 0):.0f}%",
            help=widget_help("Average analysis completion across analysed transcripts"),
        )
    with col5:
        st.metric(
            "Size on disk",
            format_bytes_display(stats.get("total_artifact_bytes", 0)),
            help=widget_help("Total size of produced analysis artifacts across all runs"),
        )


def _render_sessions() -> None:
    """Per-session table (opt-in; shares cache with detailed statistics)."""
    sessions, _stats = _cached_sessions_and_stats()
    if not sessions:
        st.info("No sessions found.")
        return
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


def _render_recent_runs() -> None:
    """Recent-run list (opt-in; walks outputs tree)."""
    runs = instrument_cached_call(
        "cached_list_recent_runs",
        cached_list_recent_runs,
        limit=10,
        bucket="home_summary",
    )
    set_count("recent_runs_returned", len(runs))

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


def render_home() -> None:
    """Render the home/dashboard page."""
    render_page_shell("Home")

    try:
        _render_transcript_overview()

        # Dynamic expanders (on_change="rerun") gate expensive work via .open —
        # collapsed bodies do not run until the user expands them.
        details = st.expander(
            "Detailed statistics",
            expanded=False,
            key=_HOME_DETAIL_STATS_KEY,
            on_change="rerun",
        )
        if details.open:
            with details:
                _render_detailed_statistics()

        sessions = st.expander(
            "Sessions",
            expanded=False,
            key=_HOME_SESSIONS_KEY,
            on_change="rerun",
        )
        if sessions.open:
            with sessions:
                _render_sessions()

        recent = st.expander(
            "Recent runs",
            expanded=False,
            key=_HOME_RECENT_RUNS_KEY,
            on_change="rerun",
        )
        if recent.open:
            with recent:
                _render_recent_runs()
    except Exception as e:
        st.error(f"Could not load dashboard: {e}")
