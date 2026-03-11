"""
Shared @st.cache_data helpers to avoid expensive recomputation on every Streamlit rerun.

Use these for list_transcripts, list_recent_runs, list_groups, module lists, and
doctor report so that dropdown/radio/widget interactions don't trigger full I/O
and the main content doesn't dim.
"""

from __future__ import annotations

import streamlit as st


@st.cache_data(ttl=120, show_spinner=False)
def cached_list_transcripts() -> list:
    from transcriptx.app.controllers.library_controller import LibraryController

    return LibraryController().list_transcripts()


@st.cache_data(show_spinner=False)
def cached_get_available_modules() -> list[str]:
    from transcriptx.app.controllers.analysis_controller import AnalysisController

    return AnalysisController().get_available_modules()


@st.cache_data(show_spinner=False)
def cached_get_default_modules(transcript_path_str: str) -> list[str]:
    from transcriptx.app.controllers.analysis_controller import AnalysisController

    return AnalysisController().get_default_modules([transcript_path_str])


@st.cache_data(show_spinner=False)
def cached_get_module_info_list() -> list:
    from transcriptx.app.module_resolution import get_module_info_list

    return get_module_info_list()


@st.cache_data(ttl=60, show_spinner=False)
def cached_list_recent_runs(limit: int = 20) -> list:
    from transcriptx.app.controllers.run_controller import RunController

    return RunController().list_recent_runs(limit=limit)


@st.cache_data(ttl=60, show_spinner=False)
def cached_doctor_report() -> dict:
    from transcriptx.app.controllers.diagnostics_controller import DiagnosticsController

    return DiagnosticsController().get_doctor_report()


@st.cache_data(ttl=60, show_spinner=False)
def cached_list_groups() -> list:
    from transcriptx.web.services.group_service import GroupService

    return GroupService.list_groups()
