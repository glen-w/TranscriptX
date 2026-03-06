"""
Home / Dashboard page for TranscriptX.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from transcriptx.app.controllers.library_controller import LibraryController
from transcriptx.app.controllers.run_controller import RunController
from transcriptx.core.utils.paths import OUTPUTS_DIR


def render_home() -> None:
    """Render the home/dashboard page."""
    st.markdown(
        '<div class="main-header">🏠 Home</div>',
        unsafe_allow_html=True,
    )

    try:
        run_ctrl = RunController()
        lib_ctrl = LibraryController()

        runs = run_ctrl.list_recent_runs(limit=10)
        transcripts = lib_ctrl.list_transcripts()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Recent Runs", len(runs))
        with col2:
            st.metric("Transcripts", len(transcripts))
        with col3:
            st.metric("Output Root", "Configured" if Path(OUTPUTS_DIR).exists() else "N/A")

        st.divider()
        st.subheader("Quick Actions")
        qc1, qc2, qc3 = st.columns(3)
        with qc1:
            if st.button("📊 Start Analysis", key="home_start_analysis"):
                st.session_state["page"] = "Run Analysis"
                st.rerun()
        with qc2:
            if st.button("📁 Open Library", key="home_open_library"):
                st.session_state["page"] = "Library"
                st.rerun()
        with qc3:
            if runs and st.button("📂 Open Latest Run", key="home_latest_run"):
                latest = runs[0]
                st.session_state["subject_type"] = "transcript"
                st.session_state["subject_id"] = latest.run_dir.parent.name
                st.session_state["run_id"] = latest.run_dir.name
                st.session_state["page"] = "Overview"
                st.rerun()

        st.divider()
        st.subheader("Recent Runs")
        if not runs:
            st.info("No analysis runs yet. Start an analysis from the Library or Run Analysis page.")
        else:
            for run in runs[:5]:
                with st.expander(f"{run.run_id} — {run.created_at.strftime('%Y-%m-%d %H:%M')}"):
                    st.caption(f"Transcript: {run.transcript_path}")
                    st.caption(f"Modules: {', '.join(run.selected_modules[:5])}{'...' if len(run.selected_modules) > 5 else ''}")
                    if st.button("Open", key=f"open_run_{run.run_id}"):
                        st.session_state["subject_type"] = "transcript"
                        st.session_state["subject_id"] = run.run_dir.parent.name
                        st.session_state["run_id"] = run.run_dir.name
                        st.session_state["page"] = "Overview"
                        st.rerun()

    except Exception as e:
        st.error(f"Could not load dashboard: {e}")
