"""Canonical navigation contracts and context normalization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from transcriptx.web.cache_helpers import cached_list_available_sessions
from transcriptx.web.services.file_service import FileService
from transcriptx.web.services.subject_service import SubjectService

RequiredContext = Literal["none", "subject", "run_scoped", "transcript_or_group"]
FallbackBehavior = Literal["stay", "home", "overview", "library", "run_analysis"]


@dataclass(frozen=True)
class PagePrerequisite:
    required_context: RequiredContext
    allowed_fallback: FallbackBehavior
    may_mutate_context: bool = False


@dataclass(frozen=True)
class PageAccessResult:
    allowed: bool
    help_text: str | None = None


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
    """Pre-select paths on Transcribe Audio and switch to that page."""
    session_state[TRANSCRIPTION_NAV_PATHS_KEY] = [str(p) for p in paths]
    session_state["transcription_active_tab"] = "Pick existing"
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
