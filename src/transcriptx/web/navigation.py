"""Canonical navigation contracts and context normalization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from transcriptx.web.cache_helpers import cached_list_available_sessions
from transcriptx.web.services.file_service import FileService
from transcriptx.web.services.subject_service import SubjectService

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
    help_text: str | None = None


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
    _spec("Run Analysis", "Run Analysis", "workflow", may_mutate_context=True),
    _spec("Batch Ops", "Batch Analysis", "workflow", may_mutate_context=False),
    _spec("Groups", "Groups", "workflow", may_mutate_context=True),
    _spec("Library", "Library", "view", may_mutate_context=True),
    _spec("Search", "Search", "view"),
    _spec("Statistics", "Statistics", "view"),
    _spec(
        "Transcript",
        "Transcript",
        "view",
        subsection="Read",
        required_context="transcript_or_group",
        allowed_fallback="home",
        may_mutate_context=True,
    ),
    _spec(
        "Overview",
        "Overview",
        "view",
        subsection="Summarise",
        required_context="run_scoped",
        allowed_fallback="home",
    ),
    _spec(
        "Insights",
        "Insights",
        "view",
        subsection="Summarise",
        required_context="run_scoped",
        allowed_fallback="overview",
    ),
    _spec(
        "Charts",
        "Charts",
        "view",
        subsection="Explore",
        required_context="run_scoped",
        allowed_fallback="overview",
    ),
    _spec(
        "Data",
        "Data",
        "view",
        subsection="Explore",
        required_context="run_scoped",
        allowed_fallback="overview",
    ),
    _spec(
        "Explorer",
        "File List",
        "view",
        subsection="Explore",
        required_context="run_scoped",
        allowed_fallback="overview",
    ),
    _spec("Corrections Studio", "Corrections Studio", "tools"),
    _spec("Audio Prep", "Audio Pre-processing", "tools"),
    _spec("Audio Merge", "Audio Merge", "tools"),
    _spec("Dashboard Builder", "Dashboard Builder", "tools"),
    _spec("Settings", "Settings", "settings"),
    _spec("Profiles", "Profiles", "settings"),
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


def page_requires_workspace_hydration(page: str | None) -> bool:
    """True when the active page needs sidebar workspace pickers / session discovery."""
    return get_page_spec(page).required_context in _HYDRATING_CONTEXTS


def pages_in_section(section: NavSection) -> list[PageSpec]:
    """Ordered sidebar pages for a nav section."""
    return [spec for spec in PAGE_SPECS if spec.section == section]


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


def session_only_context_readiness(session_state: dict[str, Any]) -> dict[str, bool]:
    """Session-only readiness booleans without filesystem/subject resolution."""
    subject_type = session_state.get("subject_type")
    subject_id = session_state.get("subject_id")
    run_id = session_state.get("run_id")
    subject_ready = bool(subject_type in ("transcript", "group") and subject_id)
    run_scoped_ready = bool(subject_ready and run_id)
    transcript_ready = bool(
        subject_ready
        and (subject_type == "group" or (subject_type == "transcript" and bool(run_id)))
    )
    return {
        "subject_ready": subject_ready,
        "run_scoped_ready": run_scoped_ready,
        "transcript_ready": transcript_ready,
    }


def _is_transcript_path(value: str | None) -> bool:
    if not value:
        return False
    try:
        resolved = Path(value).expanduser().resolve()
    except Exception:
        return False
    return resolved.suffix.lower() == ".json"


def normalize_navigation_context_from_session(session_state: dict[str, Any]) -> bool:
    """
    Transitional one-way shim: derive canonical subject context from legacy transcript path.

    Returns True when canonical context was updated.
    """
    if session_state.get("subject_type") in (
        "transcript",
        "group",
    ) and session_state.get("subject_id"):
        return False
    selected_path = session_state.get("selected_transcript_path")
    if not _is_transcript_path(selected_path):
        return False
    selected_path = str(Path(selected_path).expanduser().resolve())
    sessions = cached_list_available_sessions()
    resolved = FileService.resolve_session_for_transcript_path(selected_path, sessions)
    session_state["subject_type"] = "transcript"
    if resolved:
        slug, run_id = resolved
        session_state["subject_id"] = slug
        if not session_state.get("run_id"):
            session_state["run_id"] = run_id
    else:
        session_state["subject_id"] = selected_path
    return True


def library_transcript_index(transcripts: list, transcript_path: str | Path) -> int:
    """Return 1-based Library selectbox index, or 0 when transcript is not listed."""
    try:
        target = str(Path(transcript_path).expanduser().resolve())
    except (OSError, ValueError):
        target = str(transcript_path)
    for i, meta in enumerate(transcripts):
        try:
            if str(Path(meta.path).resolve()) == target:
                return i + 1
        except (OSError, ValueError):
            if str(meta.path) == target:
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

    apply_transcript_selection_context(session_state, str(transcript_path))
    try:
        normalized = str(Path(transcript_path).expanduser().resolve())
    except (OSError, ValueError):
        normalized = str(transcript_path)
    session_state[LIBRARY_NAV_TRANSCRIPT_PATH] = normalized


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


def apply_transcript_selection_context(
    session_state: dict[str, Any], transcript_path: str
) -> None:
    """Canonical entry-point helper for pages selecting a transcript."""
    try:
        normalized_path = str(Path(transcript_path).expanduser().resolve())
    except Exception:
        normalized_path = transcript_path
    session_state["selected_transcript_path"] = normalized_path
    sessions = cached_list_available_sessions()
    resolved = FileService.resolve_session_for_transcript_path(
        normalized_path, sessions
    )
    session_state["subject_type"] = "transcript"
    if resolved:
        session_state["subject_id"] = resolved[0]
        session_state["run_id"] = resolved[1]
    else:
        session_state["subject_id"] = normalized_path


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
        return PageAccessResult(allowed=True, help_text=None)
    required = prereq.required_context
    if required == "none":
        return PageAccessResult(allowed=True, help_text=None)
    if required == "subject":
        if readiness.get("subject_ready"):
            return PageAccessResult(allowed=True, help_text=None)
        return PageAccessResult(False, "Select a subject in the sidebar.")
    if required == "run_scoped":
        if readiness.get("run_scoped_ready"):
            return PageAccessResult(allowed=True, help_text=None)
        return PageAccessResult(False, "Select a subject and run in the sidebar.")
    if required == "transcript_or_group":
        if readiness.get("transcript_ready"):
            return PageAccessResult(allowed=True, help_text=None)
        return PageAccessResult(False, "Select a transcript/group context and run.")
    return PageAccessResult(allowed=True, help_text=None)


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
    """Open Data with a specific artifact preselected."""
    import streamlit as st

    from transcriptx.web.state import DATA_KEY_ARTIFACT_PRESET, PAGE_KEY

    st.session_state[PAGE_KEY] = "Data"
    st.session_state[DATA_KEY_ARTIFACT_PRESET] = artifact_id
    st.rerun()


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
