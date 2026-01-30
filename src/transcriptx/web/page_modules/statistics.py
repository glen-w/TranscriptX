"""
Statistics page for TranscriptX Studio.

Shows aggregate and per-session statistics across all transcript runs.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from transcriptx.web.utils import (
    get_all_sessions_statistics,
    list_available_sessions,
)


def render_statistics() -> None:
    """Render the Statistics page with aggregate and per-session stats."""
    st.markdown(
        '<div class="main-header">📊 Statistics</div>',
        unsafe_allow_html=True,
    )

    sessions = list_available_sessions()
    if not sessions:
        st.info("No transcript sessions found. Process transcripts to see statistics here.")
        return

    stats = get_all_sessions_statistics()

    # Aggregate metrics
    st.subheader("Overview")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Sessions", stats.get("total_sessions", 0))
    with col2:
        st.metric(
            "Total duration",
            f"{stats.get('total_duration_minutes', 0):.0f} min",
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
    for s in sessions:
        rows.append({
            "Session": s.get("name", ""),
            "Duration (min)": s.get("duration_minutes", 0),
            "Words": s.get("word_count", 0),
            "Segments": s.get("segment_count", 0),
            "Speakers": s.get("speaker_count", 0),
            "Completion %": s.get("analysis_completion", 0),
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
