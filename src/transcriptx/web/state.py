"""
Session state key constants for TranscriptX Streamlit app.

Use these for UI state only. Persisted data (config, profiles, runs, transcripts)
lives in filesystem/DB per storage contract.
"""

from __future__ import annotations

from typing import Any, Literal

# Selection state
PAGE_KEY = "page"
SUBJECT_TYPE_KEY = "subject_type"
SUBJECT_ID_KEY = "subject_id"
RUN_ID_KEY = "run_id"
NAV_REQUEST_KEY = "nav_request"
SELECTED_TRANSCRIPT_PATH = "selected_transcript_path"
# One-shot: Home (etc.) sets this before navigating to Library rename workflow.
LIBRARY_NAV_TRANSCRIPT_PATH = "_library_nav_transcript_path"
IMPORT_LAST_TRANSCRIPT_PATH = "import_last_transcript_path"

# Selectbox: explicit choice before loading dependent content (Streamlit has no empty selection)
SELECTBOX_PLACEHOLDER_TRANSCRIPT = "— Select a transcript —"
SELECTBOX_PLACEHOLDER_GROUP = "— Select a group —"
SELECTBOX_PLACEHOLDER_SESSION = "— Select a session —"
SELECTBOX_PLACEHOLDER_MODULE = "— Select a module —"
SELECTBOX_PLACEHOLDER_ARTIFACT = "— Select an artifact —"
SELECTED_RUN_DIR = "selected_run_dir"
SELECTED_PROFILE_NAME = "selected_profile_name"

# Analysis form
PENDING_ANALYSIS_REQUEST = "pending_analysis_request"

# Execution state
ACTIVE_JOB_ID = "active_job_id"
JOB_LOGS = "job_logs"

# UI state
UI_FILTERS = "ui_filters"
SETTINGS_DRAFT = "settings_draft"
PAGE_FLASH_MESSAGE = "page_flash_message"
PAGE_FLASH_KIND = "page_flash_kind"

# Sidebar: keyed expanders (Streamlit session_state holds open/closed when on_change="rerun")
TX_NAV_EXPANDER_WORKFLOW = "tx_nav_exp_workflow"
TX_NAV_EXPANDER_TOOLS = "tx_nav_exp_tools"
TX_NAV_EXPANDER_VIEW = "tx_nav_exp_view"
TX_NAV_EXPANDER_CONFIG = "tx_nav_exp_config"
TX_NAV_SIDEBAR_SEEDED = "tx_nav_sidebar_seeded"
TX_NAV_PREV_SHOULD_PRIORITIZE_VIEW = "tx_nav_prev_should_prioritize_view"

FlashKind = Literal["success", "info", "warning", "error"]
SubjectType = Literal["transcript", "group"]


def get_current_subject_context() -> tuple[SubjectType | None, str | None, str | None]:
    """Read canonical subject context tuple from session state."""
    import streamlit as st

    subject_type = st.session_state.get(SUBJECT_TYPE_KEY)
    if subject_type not in ("transcript", "group"):
        subject_type = None
    subject_id = st.session_state.get(SUBJECT_ID_KEY)
    run_id = st.session_state.get(RUN_ID_KEY)
    return subject_type, subject_id, run_id


def set_current_subject_context(
    *,
    subject_type: SubjectType | None,
    subject_id: str | None,
    run_id: str | None,
) -> None:
    """Write canonical subject context tuple to session state."""
    import streamlit as st

    st.session_state[SUBJECT_TYPE_KEY] = subject_type
    st.session_state[SUBJECT_ID_KEY] = subject_id
    st.session_state[RUN_ID_KEY] = run_id


def set_selected_transcript_path(path: str | None) -> None:
    """Set legacy transcript path key while migration to canonical context is in progress."""
    import streamlit as st

    st.session_state[SELECTED_TRANSCRIPT_PATH] = path


def set_page_flash(kind: FlashKind, message: str) -> None:
    """Queue a one-shot banner for the next main render (consumed in app.main)."""
    import streamlit as st

    st.session_state[PAGE_FLASH_KIND] = kind
    st.session_state[PAGE_FLASH_MESSAGE] = message


def try_page_toast(message: str) -> None:
    """Best-effort toast; no-op on older Streamlit."""
    try:
        import streamlit as st

        st.toast(message)
    except Exception:
        pass


# --- Charts gallery: session keys (single source of truth) ---

CHARTS_KEY_FILTER_MODULE = "filter_module"
CHARTS_KEY_FILTER_SCOPE = "filter_scope"
CHARTS_KEY_FILTER_SHOW_STATIC = "filter_show_static"
CHARTS_KEY_FILTER_SHOW_DYNAMIC = "filter_show_dynamic"
CHARTS_KEY_FILTER_TAGS = "filter_tags"
CHARTS_KEY_FILTER_SUBVIEW = "filter_subview"
CHARTS_KEY_FILTER_SLICE_ID = "filter_slice_id"
CHARTS_KEY_SOURCE_PRESET = "charts_source_preset"
CHARTS_KEY_SUBVIEW_TABS = "charts_subview_tabs"
CHARTS_KEY_SLICE_SELECTOR = "charts_slice_selector"
CHARTS_KEY_TAGS_MULTI = "charts_tags_multiselect"
CHARTS_KEY_STATIC_TOGGLE = "filter_static_toggle"
CHARTS_KEY_DYNAMIC_TOGGLE = "filter_dynamic_toggle"
CHARTS_KEY_EXPAND_ALL = "charts_expand_all"
CHARTS_KEY_SHOW_SUMMARY_TOGGLE = "show_summary_toggle"
CHARTS_KEY_FULL_SCREEN = "full_screen_artifact"
CHARTS_KEY_FILTERS_INIT = "tx_charts_filters_initialized_for"
CHARTS_KEY_EXPORT_RESULT = "charts_export_result"
CHARTS_KEY_EXPORT_SIG = "charts_export_signature"

DATA_KEY_ARTIFACT_PRESET = "data_artifact_preset"

CHARTS_FILTER_DEFAULTS: dict[str, Any] = {
    CHARTS_KEY_FILTER_MODULE: None,
    CHARTS_KEY_FILTER_SCOPE: None,
    CHARTS_KEY_FILTER_SHOW_STATIC: True,
    CHARTS_KEY_FILTER_SHOW_DYNAMIC: True,
    CHARTS_KEY_FILTER_TAGS: [],
    CHARTS_KEY_FILTER_SUBVIEW: None,
    CHARTS_KEY_FILTER_SLICE_ID: None,
    # Widget keys must match Streamlit widget state
    CHARTS_KEY_SOURCE_PRESET: "All",
    CHARTS_KEY_SUBVIEW_TABS: "All",
    CHARTS_KEY_SLICE_SELECTOR: "All",
    CHARTS_KEY_EXPAND_ALL: False,
    CHARTS_KEY_STATIC_TOGGLE: True,
    CHARTS_KEY_DYNAMIC_TOGGLE: True,
    CHARTS_KEY_SHOW_SUMMARY_TOGGLE: True,
    CHARTS_KEY_FULL_SCREEN: None,
    CHARTS_KEY_TAGS_MULTI: [],
    CHARTS_KEY_EXPORT_RESULT: None,
    CHARTS_KEY_EXPORT_SIG: None,
}


def charts_resettable_keys() -> list[str]:
    """Keys mutated by reset_charts_filters_to_defaults (excludes init marker)."""
    return [
        CHARTS_KEY_FILTER_MODULE,
        CHARTS_KEY_FILTER_SCOPE,
        CHARTS_KEY_FILTER_SHOW_STATIC,
        CHARTS_KEY_FILTER_SHOW_DYNAMIC,
        CHARTS_KEY_FILTER_TAGS,
        CHARTS_KEY_FILTER_SUBVIEW,
        CHARTS_KEY_FILTER_SLICE_ID,
        CHARTS_KEY_SOURCE_PRESET,
        CHARTS_KEY_SUBVIEW_TABS,
        CHARTS_KEY_SLICE_SELECTOR,
        CHARTS_KEY_EXPAND_ALL,
        CHARTS_KEY_STATIC_TOGGLE,
        CHARTS_KEY_DYNAMIC_TOGGLE,
        CHARTS_KEY_SHOW_SUMMARY_TOGGLE,
        CHARTS_KEY_FULL_SCREEN,
        CHARTS_KEY_TAGS_MULTI,
        CHARTS_KEY_EXPORT_RESULT,
        CHARTS_KEY_EXPORT_SIG,
    ]
