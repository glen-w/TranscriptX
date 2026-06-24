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
