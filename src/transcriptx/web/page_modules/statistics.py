"""
Statistics page for TranscriptX Studio.

Shows aggregate and per-session statistics across all transcript runs.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from transcriptx.web.components.page_shell import render_page_help, render_page_shell
from transcriptx.web.utils import (
    get_all_sessions_statistics,
    list_available_sessions,
)
from transcriptx.utils.text_utils import format_duration_display_from_config

_STATISTICS_HELP = (
    "**Statistics** shows workspace-wide session counts, duration, words, "
    "and analysis completion across all transcript runs."
)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_sessions_and_stats() -> tuple[list, dict]:
    sessions = list_available_sessions()
    stats = get_all_sessions_statistics()
    return sessions, stats


def render_statistics() -> None:
    """Render the Statistics page with aggregate and per-session stats."""
    render_page_shell(
        "Statistics",
        "Workspace-wide metrics across all transcript sessions.",
        badges=None,
        actions=None,
    )

    sessions, stats = _cached_sessions_and_stats()
    if not sessions:
        st.info(
            "No transcript sessions found. Process transcripts to see statistics here."
        )
        render_page_help(_STATISTICS_HELP)
        return

    st.subheader("Overview")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Sessions", stats.get("total_sessions", 0))
    with col2:
        st.metric(
            "Total duration",
            format_duration_display_from_config(stats.get("total_duration_seconds", 0)),
            help="Sum of all transcript durations",
        )
    with col3:
        st.metric("Total words", f"{stats.get('total_word_count', 0):,}")
    with col4:
        st.metric("Speakers (max)", stats.get("total_speakers", 0))
    with col5:
        st.metric(
            "Analysis completion",
            f"{stats.get('average_completion', 0):.0f}%",
            help="Average analysis completion across sessions",
        )

    st.divider()
    st.subheader("Per-session statistics")

    rows = []
    for s in sorted(
        sessions, key=lambda session: session.get("duration_seconds", 0), reverse=True
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
    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True)
    render_page_help(_STATISTICS_HELP)
