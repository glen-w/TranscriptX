"""Canonical navigation contracts and context normalization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from transcriptx.web.services.file_service import FileService
from transcriptx.web.services.subject_service import SubjectService
from transcriptx.web.services.transcript_context_resolver import (
    paths_match,
    tolerant_resolve,
)

NavSection = Literal["primary", "workflow", "view", "tools", "settings"]
RequiredContext = Literal["none", "subject", "run_scoped", "transcript_or_group"]
FallbackBehavior = Literal["stay", "home", "overview", "library", "run_analysis"]
_HYDRATING_CONTEXTS: frozenset[RequiredContext] = frozenset(
    {"subject", "run_scoped", "transcript_or_group"}
)


@dataclass(frozen=True)
class PageSpec:
    key: str
    label: str
    section: NavSection
    subsection: str | None
    required_context: RequiredContext
    allowed_fallback: FallbackBehavior
    may_mutate_context: bool = False


@dataclass(frozen=True)
class PagePrerequisite:
    required_context: RequiredContext
    allowed_fallback: FallbackBehavior
    may_mutate_context: bool = False


@dataclass(frozen=True)
class PageAccessResult:
    allowed: bool


def _spec(
    key: str,
    label: str,
    section: NavSection,
    *,
    subsection: str | None = None,
    required_context: RequiredContext = "none",
    allowed_fallback: FallbackBehavior = "stay",
    may_mutate_context: bool = False,
) -> PageSpec:
    return PageSpec(
        key=key,
        label=label,
        section=section,
        subsection=subsection,
        required_context=required_context,
        allowed_fallback=allowed_fallback,
        may_mutate_context=may_mutate_context,
    )


PAGE_SPECS: tuple[PageSpec, ...] = (
    _spec("Home", "Home", "primary"),
    _spec("Library", "Library", "primary", may_mutate_context=True),
    _spec("Search", "Search", "primary"),
    _spec("Transcribe Audio", "Transcribe Audio", "workflow", may_mutate_context=True),
    _spec(
        "Import Transcript", "Import Transcript", "workflow", may_mutate_context=True
    ),
    _spec(
        "Speaker ID",
        "Speaker Identification",
        "workflow",
        may_mutate_context=True,
    ),
    _spec("Corrections Studio", "Corrections Studio", "workflow"),
    _spec("Run Analysis", "Run Analysis", "workflow", may_mutate_context=True),
    _spec("Batch Ops", "Batch Analysis", "workflow", may_mutate_context=False),
    _spec("Groups", "Groups", "workflow", may_mutate_context=True),
    _spec(
        "Overview",
        "Overview",
        "view",
        required_context="run_scoped",
        allowed_fallback="home",
    ),
    _spec(
        "Transcript",
        "Transcript",
        "view",
        required_context="transcript_or_group",
        allowed_fallback="home",
        may_mutate_context=True,
    ),
    _spec(
        "Insights",
        "Insights",
        "view",
        required_context="run_scoped",
        allowed_fallback="overview",
    ),
    _spec(
        "Charts",
        "Charts",
        "view",
        required_context="run_scoped",
        allowed_fallback="overview",
    ),
    _spec(
        "Artifacts",
        "Artifacts",
        "view",
        required_context="run_scoped",
        allowed_fallback="overview",
    ),
    # Legacy keys retained for redirect aliases (not shown in sidebar — filtered out).
    _spec(
        "Data",
        "Data",
        "view",
        subsection="legacy",
        required_context="run_scoped",
        allowed_fallback="overview",
    ),
    _spec(
        "Explorer",
        "File List",
        "view",
        subsection="legacy",
        required_context="run_scoped",
        allowed_fallback="overview",
    ),
    _spec("Audio Prep", "Audio Pre-processing", "tools"),
    _spec("Audio Merge", "Audio Merge", "tools"),
    _spec("Settings", "Settings", "settings"),
    _spec("Profiles", "Profiles", "settings"),
    _spec("Dashboard Builder", "Dashboard Builder", "settings"),
    _spec("Diagnostics", "Diagnostics", "settings"),
)

_PAGE_SPECS_BY_KEY: dict[str, PageSpec] = {spec.key: spec for spec in PAGE_SPECS}


def get_page_spec(page: str | None) -> PageSpec:
    """Return registered page metadata, or a safe non-hydrating default for unknown keys."""
    if page and page in _PAGE_SPECS_BY_KEY:
        return _PAGE_SPECS_BY_KEY[page]
    return PageSpec(
        key=page or "Home",
        label=page or "Home",
        section="primary",
        subsection=None,
        required_context="none",
        allowed_fallback="home",
        may_mutate_context=False,
    )


# Pages where the sticky context line adds noise (launch/setup/settings).
_CONTEXT_BAR_HIDDEN_KEYS: frozenset[str] = frozenset(
    {"Home", "Transcribe Audio", "Import Transcript"}
)
_CONTEXT_BAR_HIDDEN_SECTIONS: frozenset[NavSection] = frozenset({"tools", "settings"})


def should_show_context_bar(page: str | None) -> bool:
    """Return False on Home, ingest pages, and tools/settings destinations."""
    if not page or page in _CONTEXT_BAR_HIDDEN_KEYS:
        return False
    return get_page_spec(page).section not in _CONTEXT_BAR_HIDDEN_SECTIONS


def page_requires_workspace_hydration(page: str | None) -> bool:
    """True when the active page needs sidebar workspace pickers / session discovery."""
    return get_page_spec(page).required_context in _HYDRATING_CONTEXTS


def pages_in_section(section: NavSection) -> list[PageSpec]:
    """Ordered sidebar pages for a nav section (excludes legacy redirect aliases)."""
    return [
        spec
        for spec in PAGE_SPECS
        if spec.section == section and spec.subsection != "legacy"
    ]


LEGACY_PAGE_REDIRECTS: dict[str, tuple[str, str | None]] = {
    # page_key -> (target_page, artifacts_section or None)
    "Data": ("Artifacts", "Preview"),
    "Explorer": ("Artifacts", "Browse"),
    "Statistics": ("Home", None),
}


def migrate_legacy_page_key(page: str | None) -> tuple[str, str | None]:
    """Map legacy page keys before prereq evaluation."""
    if not page:
        return "Home", None
    if page in LEGACY_PAGE_REDIRECTS:
        return LEGACY_PAGE_REDIRECTS[page]
    return page, None


def build_prerequisites() -> dict[str, PagePrerequisite]:
    """Build router prerequisites from PageSpec (single source of truth)."""
    return {
        spec.key: PagePrerequisite(
            required_context=spec.required_context,
            allowed_fallback=spec.allowed_fallback,
            may_mutate_context=spec.may_mutate_context,
        )
        for spec in PAGE_SPECS
    }


def make_session_path_resolver():
    """Build an injected session resolver using cached session listing."""
    from transcriptx.web.cache_helpers import cached_list_available_sessions

    sessions = cached_list_available_sessions()

    def _resolve(path: str) -> tuple[str, str] | None:
        return FileService.resolve_session_for_transcript_path(path, sessions)

    return _resolve


def library_transcript_index(transcripts: list, transcript_path: str | Path) -> int:
    """Return 1-based Library selectbox index, or 0 when transcript is not listed."""
    target = tolerant_resolve(transcript_path)
    for i, meta in enumerate(transcripts):
        if paths_match(meta.path, target):
            return i + 1
    return 0


TRANSCRIPTION_NAV_PATHS_KEY = "transcription_nav_paths"


def navigate_to_audio_merge_with_paths(
    session_state: dict[str, Any], paths: list[Path | str]
) -> None:
    """Pre-fill Audio Merge ordered paths and switch to the Audio Merge page."""
    session_state["audio_merge_ordered_paths"] = [str(p) for p in paths]
    session_state["page"] = "Audio Merge"


def navigate_to_transcribe_with_paths(
    session_state: dict[str, Any], paths: list[Path | str]
) -> None:
    """Open Transcribe Audio with path hints for external transcription."""
    session_state[TRANSCRIPTION_NAV_PATHS_KEY] = [str(p) for p in paths]
    session_state["page"] = "Transcribe Audio"


def consume_transcription_nav_paths(session_state: dict[str, Any]) -> list[str]:
    """Return and clear one-shot transcription path preselect from navigation."""
    nav_paths = session_state.pop(TRANSCRIPTION_NAV_PATHS_KEY, None)
    if not nav_paths:
        return []
    return [str(p) for p in nav_paths]


def navigate_to_library_rename_workflow(
    session_state: dict[str, Any], transcript_path: str | Path
) -> None:
    """Set session state for Library rename workflow and switch page to Library."""
    apply_library_rename_navigation(session_state, transcript_path)
    session_state["page"] = "Library"


def apply_library_rename_navigation(
    session_state: dict[str, Any], transcript_path: str | Path
) -> None:
    """
    Prepare session state for Library rename workflow on transcript_path.

    Sets canonical transcript context plus a one-shot preselect consumed by Library.
    """
    from transcriptx.web.state import LIBRARY_NAV_TRANSCRIPT_PATH

    SubjectService.set_transcript_context_from_path(
        session_state,
        transcript_path,
        session_resolver=make_session_path_resolver(),
    )
    session_state[LIBRARY_NAV_TRANSCRIPT_PATH] = tolerant_resolve(transcript_path)


def consume_library_transcript_nav(
    session_state: dict[str, Any],
    transcripts: list,
    *,
    library_select_key: str = "library_transcript_select",
) -> None:
    """Apply one-shot Library transcript preselect from navigation (e.g. Home Rename)."""
    from transcriptx.web.state import LIBRARY_NAV_TRANSCRIPT_PATH

    nav_path = session_state.pop(LIBRARY_NAV_TRANSCRIPT_PATH, None)
    if not nav_path:
        return
    idx = library_transcript_index(transcripts, nav_path)
    if idx > 0:
        session_state[library_select_key] = idx


def context_readiness(session_state: dict[str, Any]) -> dict[str, bool]:
    subject = SubjectService.resolve_current_subject(session_state)
    run_id = session_state.get("run_id")
    run_scoped_ready = bool(subject and run_id)
    transcript_ready = bool(
        subject
        and (
            subject.subject_type == "group"
            or (subject.subject_type == "transcript" and bool(run_id))
        )
    )
    return {
        "subject_ready": bool(subject),
        "run_scoped_ready": run_scoped_ready,
        "transcript_ready": transcript_ready,
    }


def evaluate_page_access(
    page: str,
    prerequisites: dict[str, PagePrerequisite],
    readiness: dict[str, bool],
) -> PageAccessResult:
    prereq = prerequisites.get(page)
    if prereq is None:
        return PageAccessResult(allowed=True)
    required = prereq.required_context
    if required == "none":
        return PageAccessResult(allowed=True)
    if required == "subject":
        if readiness.get("subject_ready"):
            return PageAccessResult(allowed=True)
        return PageAccessResult(allowed=False)
    if required == "run_scoped":
        if readiness.get("run_scoped_ready"):
            return PageAccessResult(allowed=True)
        return PageAccessResult(allowed=False)
    if required == "transcript_or_group":
        if readiness.get("transcript_ready"):
            return PageAccessResult(allowed=True)
        return PageAccessResult(allowed=False)
    return PageAccessResult(allowed=True)


# --- Cross-page deep links (Track B) ---


def navigate_to_charts(*, module: str | None = None) -> None:
    """Open Charts with optional module filter preset."""
    import streamlit as st

    from transcriptx.web.state import CHARTS_KEY_FILTER_MODULE, PAGE_KEY

    st.session_state[PAGE_KEY] = "Charts"
    if module:
        st.session_state[CHARTS_KEY_FILTER_MODULE] = module
    st.rerun()


def navigate_to_data_artifact(*, artifact_id: str) -> None:
    """Open Artifacts Preview with a specific artifact preselected (one-shot)."""
    import streamlit as st

    from transcriptx.web.state import (
        ARTIFACTS_KEY_PREVIEW_ID,
        ARTIFACTS_KEY_SECTION,
        DATA_KEY_ARTIFACT_PRESET,
        PAGE_KEY,
    )

    st.session_state[PAGE_KEY] = "Artifacts"
    st.session_state[ARTIFACTS_KEY_SECTION] = "Preview"
    st.session_state[ARTIFACTS_KEY_PREVIEW_ID] = artifact_id
    st.session_state[DATA_KEY_ARTIFACT_PRESET] = artifact_id
    st.session_state["_artifacts_force_preview"] = True
    st.rerun()


def navigate_to_artifact_preview(*, artifact_id: str) -> None:
    """Alias for navigate_to_data_artifact."""
    navigate_to_data_artifact(artifact_id=artifact_id)


def navigate_highlight_to_transcript(
    *,
    session_slug: str,
    run_id: str,
    segment_index: int | None = None,
    start_time: float | None = None,
    highlight_query: str | None = None,
) -> None:
    """Jump to Transcript at a highlight segment when index is known."""
    if segment_index is None:
        return
    from transcriptx.web.models.search import SegmentRef, TranscriptRef
    from transcriptx.web.page_modules.transcript import navigate_to_segment

    segment_ref = SegmentRef(
        transcript_ref=TranscriptRef(session_slug=session_slug, run_id=run_id),
        primary_locator="index",
        segment_index=segment_index,
        timecode=start_time,
    )
    navigate_to_segment(segment_ref, highlight_query=highlight_query)
