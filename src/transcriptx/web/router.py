"""Page prerequisites and routing for web app."""

from __future__ import annotations

from importlib import import_module
from typing import Any, Callable

import streamlit as st

from transcriptx.web.navigation import (
    PagePrerequisite,
    build_prerequisites,
    context_readiness,
    evaluate_page_access,
    migrate_legacy_page_key,
)
from transcriptx.web.state import ARTIFACTS_KEY_SECTION, PAGE_KEY

PAGE_PREREQUISITES: dict[str, PagePrerequisite] = build_prerequisites()

_PAGE_MODULES_PKG = "transcriptx.web.page_modules"


def _lazy_renderer(module_name: str, func_name: str) -> Callable[[], None]:
    """Import the page module on first render instead of at app startup.

    Keeps heavy page dependencies (pandas, PIL, pipeline stack) off the
    cold-start path for pages the user never opens.
    """

    def _render() -> None:
        module = import_module(f"{_PAGE_MODULES_PKG}.{module_name}")
        getattr(module, func_name)()

    return _render


def _render_home() -> None:
    from transcriptx.web.page_modules.home import render_home

    render_home()


def _render_artifacts() -> None:
    from transcriptx.web.page_modules.artifacts import render_artifacts

    render_artifacts()


def fallback_for_page(page: str) -> str | None:
    prereq = PAGE_PREREQUISITES.get(page)
    if prereq is None:
        return None
    mapping = {
        "home": "Home",
        "overview": "Overview",
        "library": "Library",
        "run_analysis": "Run Analysis",
    }
    return mapping.get(prereq.allowed_fallback)


def _redirect_legacy_data() -> None:
    """Thin alias for bookmarked Data sessions."""
    st.session_state[PAGE_KEY] = "Artifacts"
    if not st.session_state.get(ARTIFACTS_KEY_SECTION):
        st.session_state[ARTIFACTS_KEY_SECTION] = "Preview"
    _render_artifacts()


def _redirect_legacy_explorer() -> None:
    """Thin alias for bookmarked File List / Explorer sessions."""
    st.session_state[PAGE_KEY] = "Artifacts"
    st.session_state[ARTIFACTS_KEY_SECTION] = "Browse"
    _render_artifacts()


def build_page_renderers(
    *,
    corrections_studio_available: bool,
    render_corrections_studio: Callable[[], None] | None,
) -> dict[str, Callable[[], None]]:
    page_renderers: dict[str, Callable[[], None]] = {
        "Home": _render_home,
        "Library": _lazy_renderer("library", "render_library"),
        "Overview": _lazy_renderer("overview", "render_overview"),
        "Transcript": _lazy_renderer("transcript", "render_transcript_viewer"),
        "Search": _lazy_renderer("search", "render_search"),
        "Insights": _lazy_renderer("insights", "render_insights"),
        "Charts": _lazy_renderer("charts", "render_charts"),
        "Artifacts": _render_artifacts,
        "Data": _redirect_legacy_data,
        "Explorer": _redirect_legacy_explorer,
        "Run Analysis": _lazy_renderer("run_analysis", "render_run_analysis_page"),
        "Transcribe Audio": _lazy_renderer(
            "transcribe_audio", "render_transcribe_audio_page"
        ),
        "Import Transcript": _lazy_renderer(
            "upload_transcript", "render_upload_transcript_page"
        ),
        "Settings": _lazy_renderer("settings", "render_settings_page"),
        "Profiles": _lazy_renderer("profiles", "render_profiles_page"),
        "Speaker ID": _lazy_renderer("speaker_id", "render_speaker_id_page"),
        "Audio Prep": _lazy_renderer("audio_prep", "render_audio_prep_page"),
        "Audio Merge": _lazy_renderer("audio_merge", "render_audio_merge_page"),
        "Batch Ops": _lazy_renderer("batch_ops", "render_batch_ops_page"),
        "Dashboard Builder": _lazy_renderer(
            "dashboard_builder", "render_dashboard_builder"
        ),
        "Diagnostics": _lazy_renderer("diagnostics", "render_diagnostics_page"),
        "Groups": _lazy_renderer("groups", "render_groups"),
        "Speakers": lambda: st.info("Speaker pages were removed."),
        "Speaker Detail": lambda: st.info("Speaker pages were removed."),
    }
    if corrections_studio_available and render_corrections_studio:
        page_renderers["Corrections Studio"] = render_corrections_studio
    return page_renderers


def route_current_page(
    session_state: dict[str, Any],
    *,
    corrections_studio_available: bool,
    render_corrections_studio: Callable[[], None] | None,
) -> None:
    # Redirect legacy routes before prerequisite evaluation.
    raw_page = session_state.get(PAGE_KEY, "Home")
    migrated, artifacts_section = migrate_legacy_page_key(raw_page)
    if migrated != raw_page:
        session_state[PAGE_KEY] = migrated
        if artifacts_section:
            session_state[ARTIFACTS_KEY_SECTION] = artifacts_section

    readiness = context_readiness(session_state)
    current = session_state.get(PAGE_KEY, "Home")
    access = evaluate_page_access(current, PAGE_PREREQUISITES, readiness)
    effective_page = (
        current if access.allowed else (fallback_for_page(current) or "Home")
    )
    page_renderers = build_page_renderers(
        corrections_studio_available=corrections_studio_available,
        render_corrections_studio=render_corrections_studio,
    )
    renderer = page_renderers.get(effective_page)
    if renderer is None:
        st.warning(f"Unknown page: {effective_page}")
        _render_home()
    else:
        renderer()
