"""
Shared @st.cache_data helpers to avoid expensive recomputation on every Streamlit rerun.
"""

from __future__ import annotations

import streamlit as st


@st.cache_data(ttl=120, show_spinner=False)
def cached_list_transcripts(_transcripts_dir: str = "") -> list:
    from transcriptx.app.controllers.library_controller import LibraryController

    return LibraryController().list_transcripts()


def get_cached_list_transcripts() -> list:
    from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR

    return cached_list_transcripts(str(DIARISED_TRANSCRIPTS_DIR))


@st.cache_data(ttl=120, show_spinner=False)
def cached_get_transcript_summaries_for_paths(paths_key: tuple[str, ...]) -> list:
    """Return transcript summaries (segment_count, speaker_map_status) for given paths."""
    if not paths_key:
        return []
    from transcriptx.services.speaker_studio.controller import SpeakerStudioController

    controller = SpeakerStudioController()
    return controller.list_transcripts_from_paths(list(paths_key))


def clear_transcript_listing_caches() -> None:
    """
    Clear only transcript-listing related caches.

    This avoids expensive global cache invalidation on simple file rename/import actions.
    """
    cached_list_transcripts.clear()  # type: ignore[attr-defined]
    cached_get_transcript_summaries_for_paths.clear()  # type: ignore[attr-defined]


@st.cache_data(show_spinner=False)
def cached_get_available_modules() -> list[str]:
    from transcriptx.app.controllers.analysis_controller import AnalysisController

    return AnalysisController().get_available_modules()


@st.cache_data(show_spinner=False)
def cached_get_default_modules(transcript_path_str: str) -> list[str]:
    from transcriptx.app.controllers.analysis_controller import AnalysisController

    return AnalysisController().get_default_modules([transcript_path_str])


@st.cache_data(show_spinner=False)
def cached_get_default_modules_for_paths(paths: tuple[str, ...]) -> list[str]:
    from transcriptx.app.controllers.analysis_controller import AnalysisController

    return AnalysisController().get_default_modules(list(paths))


_MODULE_INFO_CACHE_ATTRS = (
    "name",
    "description",
    "category",
    "dependencies",
    "determinism_tier",
    "requirements",
    "enhancements",
    "timeout_seconds",
    "exclude_from_default",
    "post_processing_only",
    "requires_audio",
    "requires_multiple_speakers",
    "min_named_speakers",
    "supports_audio",
    "supports_group",
    "output_namespace",
    "output_version",
    "cost_tier",
    "required_extras",
)


@st.cache_data(show_spinner=False)
def cached_get_module_info_list() -> list[dict]:
    from transcriptx.app.module_resolution import get_module_info_list

    raw = get_module_info_list()
    result = []
    for m in raw:
        d = {}
        for k in _MODULE_INFO_CACHE_ATTRS:
            v = getattr(m, k, None)
            if (
                k == "required_extras"
                and hasattr(v, "__iter__")
                and not isinstance(v, (list, str))
            ):
                v = sorted(v) if v else []
            d[k] = v
        result.append(d)
    return result


@st.cache_data(ttl=60, show_spinner=False)
def cached_list_recent_runs(limit: int = 20) -> list:
    from transcriptx.app.controllers.run_controller import RunController

    return RunController().list_recent_runs(limit=limit)


@st.cache_data(ttl=60, show_spinner=False)
def cached_doctor_report() -> dict:
    from transcriptx.app.controllers.diagnostics_controller import DiagnosticsController

    return DiagnosticsController().get_doctor_report()


@st.cache_data(ttl=60, show_spinner=False)
def _cached_groups_workspace() -> tuple:
    """List loadable groups and warnings for skipped / invalid manifests."""
    from transcriptx.core.store.group_manifest_store import GroupManifestStore

    groups, warnings = GroupManifestStore().list_groups_best_effort()
    return (tuple(groups), tuple(warnings))


def cached_list_groups() -> list:
    """Groups whose manifests load successfully (invalid manifests are omitted)."""
    return list(_cached_groups_workspace()[0])


def cached_group_manifest_warnings() -> list[str]:
    """Human-readable issues for group manifests that failed to load."""
    return list(_cached_groups_workspace()[1])


def clear_group_workspace_cache() -> None:
    """Invalidate cached group listing (call after create/update/delete group)."""
    _cached_groups_workspace.clear()  # type: ignore[attr-defined]
