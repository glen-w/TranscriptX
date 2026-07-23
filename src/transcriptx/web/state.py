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
# One-shot: Home (etc.) sets this before navigating to Library rename workflow.
LIBRARY_NAV_TRANSCRIPT_PATH = "_library_nav_transcript_path"
IMPORT_LAST_TRANSCRIPT_PATH = "import_last_transcript_path"

# Sidebar workspace widget keys (must stay in sync with canonical subject/run keys)
SUBJECT_TYPE_SELECTOR_KEY = "subject_type_selector"
SUBJECT_ID_SELECTOR_KEY = "subject_id_selector"
RUN_SELECTOR_KEY = "run_selector"
_SUBJECT_TYPE_SELECTOR_LABELS: dict[str, str] = {
    "transcript": "Transcript",
    "group": "Group",
}

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


def _sync_sidebar_widget(
    session_state: dict[str, Any], key: str, value: Any | None
) -> None:
    """Align a keyed sidebar widget with canonical context, or clear it.

    ``on_click`` / pre-sidebar callers can assign the keyed value directly so
    the next render shows the navigated subject/run (action menus, deep links).
    Mid-script callers (pages after ``render_sidebar``) hit Streamlit's
    "cannot be modified after the widget is instantiated" rule — pop instead
    so the next run rehydrates from canonical ``subject_*`` / ``run_id`` keys.
    """
    try:
        if value is None or value == "":
            session_state.pop(key, None)
        else:
            session_state[key] = value
    except Exception as exc:
        # Avoid importing Streamlit here: tests pass a plain dict; the live
        # app raises StreamlitAPIException only for already-instantiated keys.
        if type(exc).__name__ != "StreamlitAPIException":
            raise
        session_state.pop(key, None)


def apply_subject_context(
    session_state: dict[str, Any],
    *,
    subject_type: SubjectType | None,
    subject_id: str | None,
    run_id: str | None,
) -> None:
    """Write canonical subject context and sync sidebar picker widgets.

    Streamlit keeps prior selectbox values under widget keys. External
    navigators that only update ``subject_id`` / ``run_id`` would otherwise
    be overwritten by stale picker state on the next rerun (Charts/Artifacts
    then fail run-scoped access and fall back to Overview). Assigning the
    picker keys to the new identity keeps the nav-bar dropdowns in sync so
    subsequent sidebar nav stays enabled for that run.
    """
    session_state[SUBJECT_TYPE_KEY] = subject_type
    session_state[SUBJECT_ID_KEY] = subject_id
    session_state[RUN_ID_KEY] = run_id
    label = _SUBJECT_TYPE_SELECTOR_LABELS.get(subject_type or "")
    if label is not None:
        _sync_sidebar_widget(session_state, SUBJECT_TYPE_SELECTOR_KEY, label)
    # Transcript/group selectbox options use "" as the placeholder; store the
    # canonical id (or clear) so the widget does not keep a stale selection.
    _sync_sidebar_widget(session_state, SUBJECT_ID_SELECTOR_KEY, subject_id)
    _sync_sidebar_widget(session_state, RUN_SELECTOR_KEY, run_id)


def set_current_subject_context(
    *,
    subject_type: SubjectType | None,
    subject_id: str | None,
    run_id: str | None,
) -> None:
    """Write canonical subject context tuple to session state."""
    import streamlit as st

    apply_subject_context(
        st.session_state,
        subject_type=subject_type,
        subject_id=subject_id,
        run_id=run_id,
    )


def set_page_flash(kind: FlashKind, message: str) -> None:
    """Queue a one-shot banner for the next page shell render (under title/description)."""
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
CHARTS_KEY_KIND_PILLS = "charts_kind_pills"
CHARTS_KEY_SEARCH = "charts_search"
CHARTS_KEY_MODULE_SORT = "charts_module_sort"
CHARTS_KEY_CHART_TEXT = "charts_chart_text"
CHARTS_KEY_OPEN_MODULES = "charts_open_modules"
CHARTS_KEY_SECTION = "charts_gallery_section"
# Legacy display toggles — migrated once into CHARTS_KEY_CHART_TEXT, then ignored.
CHARTS_KEY_SHOW_CHART_DESCRIPTIONS = "show_chart_descriptions_toggle"
CHARTS_KEY_SHOW_LLM_SUMMARIES = "show_llm_summaries_toggle"
CHARTS_KEY_FULL_SCREEN = "full_screen_artifact"
CHARTS_KEY_FILTERS_INIT = "tx_charts_filters_initialized_for"
CHARTS_KEY_EXPORT_RESULT = "charts_export_result"
CHARTS_KEY_EXPORT_SIG = "charts_export_signature"

CHARTS_SORT_MODULE_FAMILY = "module_family"
CHARTS_SORT_ALPHA = "alpha"
CHARTS_CHART_TEXT_NONE = "None"
CHARTS_CHART_TEXT_DESCRIPTION = "Description"
CHARTS_CHART_TEXT_LLM = "LLM summary"
CHARTS_CHART_TEXT_BOTH = "Both"
CHARTS_KIND_STATIC = "Static"
CHARTS_KIND_DYNAMIC = "Dynamic"
CHARTS_SECTION_OVERVIEW = "Run overview"
CHARTS_SECTION_BROWSE = "Browse charts"

DATA_KEY_ARTIFACT_PRESET = "data_artifact_preset"

# Artifacts page (Browse / Preview / Export)
ARTIFACTS_KEY_SECTION = "artifacts_section"
ARTIFACTS_KEY_SELECTED_IDS = "artifacts_selected_ids"
ARTIFACTS_KEY_PREVIEW_ID = "artifacts_preview_id"
ARTIFACTS_KEY_SCOPE = "artifacts_selection_scope"
ARTIFACTS_KEY_SHOW_MORE = "artifacts_show_more"
ARTIFACTS_KEY_SOURCE_FILTER = "artifacts_source_filter"


def reconcile_artifact_selection(
    session_state: Any,
    *,
    subject_type: str | None,
    subject_id: str | None,
    run_id: str | None,
) -> None:
    """Clear artifact selection when subject/run changes."""
    scope = (subject_type or "", subject_id or "", run_id or "")
    prev = session_state.get(ARTIFACTS_KEY_SCOPE)
    if prev != scope:
        session_state[ARTIFACTS_KEY_SCOPE] = scope
        session_state[ARTIFACTS_KEY_SELECTED_IDS] = []
        session_state[ARTIFACTS_KEY_PREVIEW_ID] = None
        session_state[ARTIFACTS_KEY_SHOW_MORE] = None


def consume_artifact_preset(session_state: Any) -> str | None:
    """One-shot artifact preset (legacy data_artifact_preset)."""
    preset = session_state.pop(DATA_KEY_ARTIFACT_PRESET, None)
    if preset:
        return str(preset)
    return None


# Resettable filter defaults only (dirty detection + Reset). Not view prefs / ephemeral.
CHARTS_FILTER_DEFAULTS: dict[str, Any] = {
    CHARTS_KEY_FILTER_MODULE: None,
    CHARTS_KEY_FILTER_SCOPE: None,
    CHARTS_KEY_FILTER_SHOW_STATIC: True,
    CHARTS_KEY_FILTER_SHOW_DYNAMIC: True,
    CHARTS_KEY_FILTER_TAGS: [],
    CHARTS_KEY_FILTER_SUBVIEW: None,
    CHARTS_KEY_FILTER_SLICE_ID: None,
    CHARTS_KEY_SOURCE_PRESET: "All",
    CHARTS_KEY_SUBVIEW_TABS: "All",
    CHARTS_KEY_SLICE_SELECTOR: "All",
    CHARTS_KEY_STATIC_TOGGLE: True,
    CHARTS_KEY_DYNAMIC_TOGGLE: True,
    CHARTS_KEY_KIND_PILLS: [CHARTS_KIND_STATIC, CHARTS_KIND_DYNAMIC],
    CHARTS_KEY_TAGS_MULTI: [],
    CHARTS_KEY_SEARCH: "",
    CHARTS_KEY_MODULE_SORT: CHARTS_SORT_MODULE_FAMILY,
}

# Persistent view preference (not resettable, not dirty).
CHARTS_VIEW_PREF_DEFAULTS: dict[str, Any] = {
    CHARTS_KEY_CHART_TEXT: CHARTS_CHART_TEXT_BOTH,
    CHARTS_KEY_SECTION: CHARTS_SECTION_OVERVIEW,
}


def charts_resettable_keys() -> list[str]:
    """Filter keys restored by Reset and compared for dirty detection."""
    return list(CHARTS_FILTER_DEFAULTS.keys())


def charts_run_change_reset_keys() -> list[str]:
    """Filter keys cleared on subject/run change (sort is preserved)."""
    return [k for k in charts_resettable_keys() if k != CHARTS_KEY_MODULE_SORT]
