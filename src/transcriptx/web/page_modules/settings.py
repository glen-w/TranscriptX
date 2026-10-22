"""
Settings hub — session resolution, tab selection, and active panel only.

Streamlit ``st.tabs`` executes every tab body on each visit; this hub uses a
segmented control so only the selected panel runs (Settings open cost).
"""

from __future__ import annotations

import streamlit as st

from transcriptx.web.services import RunIndex, SubjectService
from transcriptx.web.ui.settings import (
    render_analysis_presets_panel,
    render_configuration_panel,
    render_corrections_panel,
    render_interface_panel,
    render_keywords_panel,
    render_models_panel,
    render_questions_panel,
    render_speakers_panel,
    render_storage_panel,
    render_watcher_panel,
)

_SETTINGS_TAB_KEY = "settings_hub_selected_tab"

_SETTINGS_TABS: tuple[str, ...] = (
    "Configuration",
    "Analysis",
    "Storage",
    "Watcher",
    "Speakers",
    "Interface",
    "Models",
    "Questions",
    "Keywords",
    "Corrections",
)


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

    tab_labels = list(_SETTINGS_TABS)
    selected = st.session_state.get(_SETTINGS_TAB_KEY)
    if selected not in tab_labels:
        st.session_state[_SETTINGS_TAB_KEY] = tab_labels[0]

    label = st.segmented_control(
        "Settings section",
        options=tab_labels,
        key=_SETTINGS_TAB_KEY,
        label_visibility="collapsed",
    )
    if label not in tab_labels:
        label = tab_labels[0]
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
        elif label == "Watcher":
            render_watcher_panel()
        elif label == "Speakers":
            render_speakers_panel()
        elif label == "Interface":
            render_interface_panel()
        elif label == "Models":
            render_models_panel()
        elif label == "Questions":
            render_questions_panel()
        elif label == "Keywords":
            render_keywords_panel()
        elif label == "Corrections":
            render_corrections_panel()
    except Exception as e:
        st.error(f"Could not load {label}: {e}")
