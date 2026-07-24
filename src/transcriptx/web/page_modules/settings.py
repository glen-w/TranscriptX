"""
Settings hub — session resolution, tabs, and panel calls only.
"""

from __future__ import annotations

import streamlit as st

from transcriptx.web.presentation.prefs import MODE_GUIDED
from transcriptx.web.presentation.resolve import resolve_presentation_mode
from transcriptx.web.presentation.switch import render_presentation_mode_switch
from transcriptx.web.presentation.visibility import (
    FULL_SETTINGS_TABS,
    GUIDED_SETTINGS_TABS,
)
from transcriptx.web.services import RunIndex, SubjectService
from transcriptx.web.ui.settings import (
    render_analysis_presets_panel,
    render_configuration_panel,
    render_interface_panel,
    render_models_panel,
    render_questions_panel,
    render_speakers_panel,
    render_storage_panel,
)

_SETTINGS_TAB_KEY = "settings_hub_selected_tab"


def render_settings_page() -> None:
    """Render the settings page (hub)."""
    st.markdown(
        '<div class="main-header">Settings</div>',
        unsafe_allow_html=True,
    )

    # Presentation switch lives outside tabs that Guided may hide.
    with st.container():
        st.subheader("Presentation")
        render_presentation_mode_switch(location="settings")

    from transcriptx.web.demo_ui import render_settings_demo_controls

    render_settings_demo_controls()

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

    mode = resolve_presentation_mode()
    tab_labels = list(
        GUIDED_SETTINGS_TABS if mode == MODE_GUIDED else FULL_SETTINGS_TABS
    )
    # Normalise stale selected-tab state when Full-only tabs disappear.
    selected = st.session_state.get(_SETTINGS_TAB_KEY)
    if selected not in tab_labels:
        st.session_state[_SETTINGS_TAB_KEY] = tab_labels[0]

    tabs = st.tabs(tab_labels)
    for tab, label in zip(tabs, tab_labels):
        with tab:
            st.session_state[_SETTINGS_TAB_KEY] = label
            try:
                if label == "Configuration":
                    render_configuration_panel(
                        run_dir=run_dir,
                        subject_display=subject_display,
                        run_display=run_display,
                    )
                elif label == "Analysis":
                    render_analysis_presets_panel()
                elif label == "Storage":
                    render_storage_panel()
                elif label == "Speakers":
                    render_speakers_panel()
                elif label == "Interface":
                    render_interface_panel()
                elif label == "Models":
                    render_models_panel()
                elif label == "Questions":
                    render_questions_panel()
            except Exception as e:
                st.error(f"Could not load {label}: {e}")
