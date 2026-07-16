"""
Settings hub — session resolution, tabs, and panel calls only.
"""

from __future__ import annotations

import streamlit as st

from transcriptx.web.services import RunIndex, SubjectService
from transcriptx.web.ui.settings import render_configuration_panel, render_storage_panel


def render_settings_page() -> None:
    """Render the settings page (hub)."""
    st.markdown(
        '<div class="main-header">Settings</div>',
        unsafe_allow_html=True,
    )

    subject = SubjectService.resolve_current_subject(st.session_state)
    run_id = st.session_state.get("run_id")
    run_dir = None
    subject_display: str | None = None
    run_display: str | None = None
    if subject and run_id:
        run_dir = RunIndex.get_run_root(
            subject.scope, run_id, subject_id=subject.subject_id
        )
        subject_display = subject.display.name
        run_display = run_id

    tab_cfg, tab_stor = st.tabs(["Configuration", "Storage"])
    try:
        with tab_cfg:
            render_configuration_panel(
                run_dir=run_dir,
                subject_display=subject_display,
                run_display=run_display,
            )
        with tab_stor:
            render_storage_panel()
    except Exception as e:
        st.error(f"Could not load settings: {e}")
