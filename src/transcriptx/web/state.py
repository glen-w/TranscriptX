"""
Session state key constants for TranscriptX Streamlit app.

Use these for UI state only. Persisted data (config, profiles, runs, transcripts)
lives in filesystem/DB per storage contract.
"""

from __future__ import annotations

from typing import Any, Literal

# Selection state
SELECTED_TRANSCRIPT_PATH = "selected_transcript_path"

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

FlashKind = Literal["success", "info", "warning", "error"]


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
