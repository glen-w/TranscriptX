"""Page prerequisites and routing for web app."""

from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from transcriptx.web.navigation import (
    PagePrerequisite,
    build_prerequisites,
    context_readiness,
    evaluate_page_access,
)
from transcriptx.web.page_modules.audio_merge import render_audio_merge_page
from transcriptx.web.page_modules.audio_prep import render_audio_prep_page
from transcriptx.web.page_modules.batch_ops import render_batch_ops_page
from transcriptx.web.page_modules.charts import render_charts
from transcriptx.web.page_modules.data import render_data
from transcriptx.web.page_modules.dashboard_builder import render_dashboard_builder
from transcriptx.web.page_modules.diagnostics import render_diagnostics_page
from transcriptx.web.page_modules.explorer import render_explorer
from transcriptx.web.page_modules.groups import render_groups
from transcriptx.web.page_modules.home import render_home
from transcriptx.web.page_modules.insights import render_insights
from transcriptx.web.page_modules.library import render_library
from transcriptx.web.page_modules.overview import render_overview
from transcriptx.web.page_modules.profiles import render_profiles_page
from transcriptx.web.page_modules.run_analysis import render_run_analysis_page
from transcriptx.web.page_modules.search import render_search
from transcriptx.web.page_modules.settings import render_settings_page
from transcriptx.web.page_modules.speaker_id import render_speaker_id_page
from transcriptx.web.page_modules.statistics import render_statistics
from transcriptx.web.page_modules.transcribe_audio import render_transcribe_audio_page
from transcriptx.web.page_modules.transcript import render_transcript_viewer
from transcriptx.web.page_modules.upload_transcript import render_upload_transcript_page
from transcriptx.web.state import PAGE_KEY

PAGE_PREREQUISITES: dict[str, PagePrerequisite] = build_prerequisites()


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


def build_page_renderers(
    *,
    corrections_studio_available: bool,
    render_corrections_studio: Callable[[], None] | None,
) -> dict[str, Callable[[], None]]:
    page_renderers: dict[str, Callable[[], None]] = {
        "Home": render_home,
        "Library": render_library,
        "Overview": render_overview,
        "Transcript": render_transcript_viewer,
        "Search": render_search,
        "Insights": render_insights,
        "Charts": render_charts,
        "Data": render_data,
        "Explorer": render_explorer,
        "Run Analysis": render_run_analysis_page,
        "Transcribe Audio": render_transcribe_audio_page,
        "Import Transcript": render_upload_transcript_page,
        "Settings": render_settings_page,
        "Profiles": render_profiles_page,
        "Speaker ID": render_speaker_id_page,
        "Audio Prep": render_audio_prep_page,
        "Audio Merge": render_audio_merge_page,
        "Batch Ops": render_batch_ops_page,
        "Dashboard Builder": render_dashboard_builder,
        "Diagnostics": render_diagnostics_page,
        "Groups": render_groups,
        "Statistics": render_statistics,
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
        render_home()
    else:
        renderer()
