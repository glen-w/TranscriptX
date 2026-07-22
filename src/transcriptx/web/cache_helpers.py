"""
Shared @st.cache_data helpers to avoid expensive recomputation on every Streamlit rerun.

Cache policy tiers (implementation stays distributed until a later pass):
1. hot-path discovery — session/transcript listing (this module)
2. metadata/index — search speaker index, run index
3. expensive artifact/content — manifests, artifact health
4. page-local UI-only — page modules until consolidated
"""

from __future__ import annotations

import streamlit as st

from transcriptx.web.perf import mark_cache_miss


@st.cache_data(ttl=120, show_spinner=False)
def cached_list_available_sessions() -> list[dict]:
    """Cached session scan for sidebar/navigation (web layer only).

    TTL is aligned with cached_list_transcripts so both hot-path scans expire
    together instead of causing staggered slow reruns.
    """
    mark_cache_miss("cached_list_available_sessions")
    from transcriptx.web.services.file_service import FileService

    return FileService.list_available_sessions()


def _transcript_metadata_signature(path) -> tuple[float, int, float]:
    """(file mtime, size, speaker-map sidecar mtime) for metadata cache keying."""
    import os

    try:
        file_stat = os.stat(path)
        mtime, size = file_stat.st_mtime, file_stat.st_size
    except OSError:
        mtime, size = 0.0, 0
    sidecar_mtime = 0.0
    try:
        from transcriptx.io.speaker_map_resolver import speaker_map_sidecar_candidates

        for candidate in speaker_map_sidecar_candidates(path):
            try:
                sidecar_mtime = candidate.stat().st_mtime
                break
            except OSError:
                continue
    except Exception:
        pass
    return mtime, size, sidecar_mtime


@st.cache_data(ttl=300, show_spinner=False)
def _cached_transcript_metadata(path_str: str, signature: tuple[float, int, float]):
    """Per-file library metadata; unchanged files skip segment re-parsing."""
    mark_cache_miss("cached_transcript_metadata")
    from pathlib import Path

    from transcriptx.app.controllers.library_controller import LibraryController

    return LibraryController().get_transcript_metadata(Path(path_str))


@st.cache_data(ttl=120, show_spinner=False)
def cached_list_transcripts(_transcripts_dir: str = "") -> list:
    mark_cache_miss("cached_list_transcripts")
    from transcriptx.app.models.errors import PathConfigError
    from transcriptx.core.utils.file_discovery import (
        discover_managed_transcript_paths,
    )

    try:
        paths = discover_managed_transcript_paths(None)
        return [
            _cached_transcript_metadata(str(p), _transcript_metadata_signature(p))
            for p in paths
        ]
    except PathConfigError:
        raise
    except Exception as e:
        raise PathConfigError(str(e)) from e


def get_cached_list_transcripts() -> list:
    from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR

    return cached_list_transcripts(str(DIARISED_TRANSCRIPTS_DIR))


@st.cache_data(ttl=120, show_spinner=False)
def cached_count_managed_transcripts(_transcripts_dir: str = "") -> int:
    """Library inventory size without loading per-file metadata."""
    mark_cache_miss("cached_count_managed_transcripts")
    from transcriptx.app.models.errors import PathConfigError
    from transcriptx.core.utils.file_discovery import discover_managed_transcript_paths

    try:
        return len(discover_managed_transcript_paths(None))
    except PathConfigError:
        raise
    except Exception as e:
        raise PathConfigError(str(e)) from e


def get_cached_count_managed_transcripts() -> int:
    from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR

    return cached_count_managed_transcripts(str(DIARISED_TRANSCRIPTS_DIR))


def _list_transcript_summaries_for_paths(paths: list[str]) -> list:
    """Read-only listing via SegmentIndexService (no ClipService / executors)."""
    from pathlib import Path

    from transcriptx.services.speaker_studio.segment_index import SegmentIndexService

    index = SegmentIndexService()
    summaries = []
    seen: set[str] = set()
    for path in paths:
        summary = index.summary_for_path(path)
        if summary is None:
            continue
        key = str(Path(summary.path).resolve())
        if key in seen:
            continue
        seen.add(key)
        summaries.append(summary)
    return sorted(summaries, key=lambda s: s.path)


@st.cache_data(ttl=120, show_spinner=False)
def cached_get_transcript_summaries_for_paths(paths_key: tuple[str, ...]) -> list:
    """Return transcript summaries (segment_count, speaker_map_status) for given paths."""
    mark_cache_miss("cached_get_transcript_summaries_for_paths")
    if not paths_key:
        return []
    return _list_transcript_summaries_for_paths(list(paths_key))


@st.cache_data(ttl=120, show_spinner=False)
def cached_list_all_transcript_summaries() -> list:
    """Fallback listing of all loadable transcripts (non-canonical included)."""
    mark_cache_miss("cached_list_all_transcript_summaries")
    from transcriptx.services.speaker_studio.segment_index import SegmentIndexService

    return SegmentIndexService().list_transcripts(canonical_only=False)


@st.cache_data(ttl=60, show_spinner=False)
def cached_list_runs(
    scope_type: str,
    subject_id: str | None = None,
    group_uuid: str | None = None,
) -> list:
    """Cached run listing for the sidebar run picker (dir scan + manifest checks)."""
    mark_cache_miss("cached_list_runs")
    from types import SimpleNamespace

    from transcriptx.web.services.run_index import RunIndex

    scope = SimpleNamespace(scope_type=scope_type, uuid=group_uuid)
    return RunIndex.list_runs(scope, subject_id=subject_id)


def clear_run_listing_caches() -> None:
    """Invalidate cached run listings (call after an analysis run completes)."""
    cached_list_runs.clear()  # type: ignore[attr-defined]
    cached_list_recent_runs.clear()  # type: ignore[attr-defined]


@st.cache_data(ttl=60, show_spinner=False)
def _cached_resolve_transcript_path(
    session_name: str, outputs_dir: str, transcripts_dir: str
) -> str | None:
    """Cached session -> transcript path resolution (manifest reads + path probes)."""
    mark_cache_miss("cached_resolve_transcript_path")
    from transcriptx.web.services.file_service import FileService

    path = FileService.resolve_transcript_path(session_name)
    return str(path) if path is not None else None


def cached_resolve_transcript_path(session_name: str) -> str | None:
    """Resolve a session name to its transcript path via a short-lived cache.

    Callers must verify the returned path still exists (renames can leave the
    cache stale within the TTL) and fall back to a direct resolve when it doesn't.
    """
    from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR, OUTPUTS_DIR

    return _cached_resolve_transcript_path(
        session_name, str(OUTPUTS_DIR), str(DIARISED_TRANSCRIPTS_DIR)
    )


def clear_transcript_listing_caches() -> None:
    """
    Clear only transcript-listing related caches.

    This avoids expensive global cache invalidation on simple file rename/import actions.
    """
    cached_list_available_sessions.clear()  # type: ignore[attr-defined]
    cached_list_transcripts.clear()  # type: ignore[attr-defined]
    cached_count_managed_transcripts.clear()  # type: ignore[attr-defined]
    cached_get_transcript_summaries_for_paths.clear()  # type: ignore[attr-defined]
    cached_list_all_transcript_summaries.clear()  # type: ignore[attr-defined]
    _cached_resolve_transcript_path.clear()  # type: ignore[attr-defined]
    _cached_transcript_metadata.clear()  # type: ignore[attr-defined]


def clear_rename_related_caches() -> None:
    """Invalidate caches that can show stale names/paths after a transcript rename."""
    clear_transcript_listing_caches()
    cached_list_recent_runs.clear()  # type: ignore[attr-defined]
    cached_list_runs.clear()  # type: ignore[attr-defined]


@st.cache_data(show_spinner=False)
def cached_get_available_modules() -> list[str]:
    mark_cache_miss("cached_get_available_modules")
    from transcriptx.app.controllers.analysis_controller import AnalysisController
    from transcriptx.web.module_ui_groups import order_module_ids

    raw = AnalysisController().get_available_modules()
    return order_module_ids(raw)


@st.cache_data(show_spinner=False)
def cached_get_default_modules(transcript_path_str: str) -> list[str]:
    mark_cache_miss("cached_get_default_modules")
    from transcriptx.app.controllers.analysis_controller import AnalysisController

    return AnalysisController().get_default_modules([transcript_path_str])


@st.cache_data(show_spinner=False)
def cached_get_default_modules_for_paths(
    paths: tuple[str, ...], *, for_group: bool = False
) -> list[str]:
    mark_cache_miss("cached_get_default_modules_for_paths")
    from transcriptx.app.controllers.analysis_controller import AnalysisController

    return AnalysisController().get_default_modules(list(paths), for_group=for_group)


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
    "requires_llm",
    "finalize_phase",
    "requires_multiple_speakers",
    "min_named_speakers",
    "gate_on_turn_taking_speakers",
    "supports_audio",
    "supports_group",
    "output_namespace",
    "output_version",
    "cost_tier",
    "required_extras",
    "extras_detected",
)


@st.cache_data(show_spinner=False)
def cached_get_module_info_list() -> list[dict]:
    mark_cache_miss("cached_get_module_info_list")
    from transcriptx.app.module_resolution import get_module_info_list
    from transcriptx.core.pipeline.optional_extras import is_extra_distribution_present
    from transcriptx.web.module_ui_groups import order_module_ids

    raw = get_module_info_list()
    result = []
    for m in raw:
        d = {}
        for k in _MODULE_INFO_CACHE_ATTRS:
            if k == "extras_detected":
                continue
            v = getattr(m, k, None)
            if (
                k == "required_extras"
                and hasattr(v, "__iter__")
                and not isinstance(v, (list, str))
            ):
                v = sorted(v) if v else []
            d[k] = v
        # Non-importing package detection for catalogue / install guidance.
        extras = d.get("required_extras") or []
        if isinstance(extras, (list, tuple, set)):
            d["extras_detected"] = {
                extra: is_extra_distribution_present(str(extra)) for extra in extras
            }
        else:
            d["extras_detected"] = {}
        result.append(d)
    names = [row["name"] for row in result if row.get("name")]
    order = order_module_ids(names)
    rank = {name: i for i, name in enumerate(order)}
    result.sort(
        key=lambda row: (
            rank.get(row.get("name"), 10**9),
            row.get("name") or "",
        )
    )
    return result


@st.cache_data(ttl=60, show_spinner=False)
def cached_list_recent_runs(limit: int = 20) -> list:
    mark_cache_miss("cached_list_recent_runs")
    from transcriptx.app.controllers.run_controller import RunController

    return RunController().list_recent_runs(limit=limit)


@st.cache_data(ttl=60, show_spinner=False)
def cached_doctor_report() -> dict:
    mark_cache_miss("cached_doctor_report")
    from transcriptx.app.controllers.diagnostics_controller import DiagnosticsController

    return DiagnosticsController().get_doctor_report()


@st.cache_data(ttl=60, show_spinner=False)
def _cached_groups_workspace() -> tuple:
    """List loadable groups and warnings for skipped / invalid manifests."""
    mark_cache_miss("cached_list_groups")
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
