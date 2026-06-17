"""
Home / Dashboard page for TranscriptX.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from transcriptx.core.utils.paths import OUTPUTS_DIR
from transcriptx.web.cache_helpers import (
    cached_list_groups,
    cached_list_recent_runs,
    get_cached_list_transcripts,
)
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_help, render_page_shell
from transcriptx.web.sidebar_options import _slug_display_labels_from_index

_HOME_HELP = "**Home** is the landing page. Use the header actions or **Recent Runs** to open analysis."


def render_home() -> None:
    """Render the home/dashboard page."""
    render_page_shell(
        "Home",
        "Workspace snapshot: transcripts, groups, and recent runs.",
        badges=None,
        actions=None,
    )

    try:
        runs = cached_list_recent_runs(limit=10)
        transcripts = get_cached_list_transcripts()
        groups = cached_list_groups()

        last_run_label = "—"
        if runs:
            last_run_label = runs[0].created_at.strftime("%Y-%m-%d %H:%M")

        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            st.markdown(
                '<div class="stat-card"><strong>Transcripts</strong><br/>'
                f"<span style='font-size:1.4rem'>{len(transcripts)}</span></div>",
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                '<div class="stat-card"><strong>Groups</strong><br/>'
                f"<span style='font-size:1.4rem'>{len(groups)}</span></div>",
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(
                '<div class="stat-card"><strong>Recent runs</strong><br/>'
                f"<span style='font-size:1.4rem'>{len(runs)}</span></div>",
                unsafe_allow_html=True,
            )
        with col4:
            st.markdown(
                '<div class="stat-card"><strong>Last run</strong><br/>'
                f"<span style='font-size:0.95rem'>{last_run_label}</span></div>",
                unsafe_allow_html=True,
            )
        with col5:
            out_ok = Path(OUTPUTS_DIR).exists()
            st.markdown(
                '<div class="stat-card"><strong>Output root</strong><br/>'
                f"<span style='font-size:0.95rem'>{'OK' if out_ok else 'N/A'}</span></div>",
                unsafe_allow_html=True,
            )
        with col6:
            st.markdown(
                '<div class="stat-card"><strong>Modules</strong><br/>'
                "<span style='font-size:0.85rem'>Run Analysis</span></div>",
                unsafe_allow_html=True,
            )

        st.divider()
        st.subheader("Recent Runs")
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
            for run in runs[:5]:
                slug = run.run_dir.parent.name
                transcript_name = slug_labels.get(slug)
                if not transcript_name:
                    transcript_name = (
                        run.transcript_path.stem
                        if run.transcript_path and run.transcript_path.name
                        else slug
                    )
                with st.expander(
                    f"{transcript_name} — {run.run_id} — "
                    f"{run.created_at.strftime('%Y-%m-%d %H:%M')}"
                ):
                    st.caption(f"Transcript: {run.transcript_path}")
                    st.caption(
                        f"Modules: {', '.join(run.selected_modules[:5])}{'...' if len(run.selected_modules) > 5 else ''}"
                    )
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("Overview", key=f"home_run_ov_{run.run_id}"):
                            st.session_state["subject_type"] = "transcript"
                            st.session_state["subject_id"] = run.run_dir.parent.name
                            st.session_state["run_id"] = run.run_dir.name
                            st.session_state["page"] = "Overview"
                            st.rerun()
                    with c2:
                        if st.button("Charts", key=f"home_run_ch_{run.run_id}"):
                            st.session_state["subject_type"] = "transcript"
                            st.session_state["subject_id"] = run.run_dir.parent.name
                            st.session_state["run_id"] = run.run_dir.name
                            st.session_state["page"] = "Charts"
                            st.rerun()
                    with c3:
                        if st.button("Data", key=f"home_run_dt_{run.run_id}"):
                            st.session_state["subject_type"] = "transcript"
                            st.session_state["subject_id"] = run.run_dir.parent.name
                            st.session_state["run_id"] = run.run_dir.name
                            st.session_state["page"] = "Data"
                            st.rerun()

        render_page_help(_HOME_HELP)
    except Exception as e:
        st.error(f"Could not load dashboard: {e}")
        render_page_help(_HOME_HELP)
