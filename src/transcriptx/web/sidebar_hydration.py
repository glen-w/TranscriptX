"""Pure sidebar workspace state resolution (no Streamlit imports)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from transcriptx.web.services.run_index import RunSummary
from transcriptx.web.services.subject_service import ResolvedSubject

SidebarStatus = Literal["loading", "empty", "ready", "no_subject"]


@dataclass(frozen=True)
class HydratedSidebarState:
    subject_type: str
    subject_id: str | None
    run_id: str | None
    transcript_options: list[str] | None
    group_keys: list[str] | None
    run_options: list[str] | None
    status: SidebarStatus


def resolve_selected_transcript(
    session_state: dict[str, Any], options: list[str]
) -> str | None:
    """Return validated transcript subject_id or None for placeholder selection."""
    if not options:
        return None
    current = session_state.get("subject_id")
    if current and current in options:
        return current
    return None


def resolve_selected_run(
    session_state: dict[str, Any], run_options: list[str]
) -> str | None:
    """Return validated run_id, first available when stale, or None."""
    if not run_options:
        return None
    current = session_state.get("run_id")
    if current and current in run_options:
        return current
    return run_options[0]


def hydrate_sidebar_state(
    session_state: dict[str, Any],
    *,
    subject_type: str,
    explicit_request: bool,
    transcript_options: list[str],
    groups: list[Any],
    resolved_subject: ResolvedSubject | None,
    runs: list[RunSummary],
) -> HydratedSidebarState:
    """Orchestrate transcript/group/run resolution for sidebar workspace UI."""
    run_options = [r.run_id for r in runs] if resolved_subject else []

    if subject_type == "transcript":
        group_keys = None
        options = transcript_options
        subject_id = resolve_selected_transcript(session_state, options)
        if explicit_request and not options:
            status: SidebarStatus = "loading"
        elif not options:
            status = "empty"
        elif resolved_subject is None and session_state.get("subject_id"):
            status = "no_subject"
        else:
            status = "ready"
    else:
        options = None
        group_keys = [g.uuid for g in groups]
        subject_id = resolve_selected_transcript(session_state, group_keys)
        if explicit_request and not groups:
            status = "loading"
        elif not groups:
            status = "empty"
        elif resolved_subject is None and session_state.get("subject_id"):
            status = "no_subject"
        else:
            status = "ready"

    run_id = resolve_selected_run(session_state, run_options) if run_options else None

    return HydratedSidebarState(
        subject_type=subject_type,
        subject_id=subject_id,
        run_id=run_id,
        transcript_options=options,
        group_keys=group_keys,
        run_options=run_options if run_options else None,
        status=status,
    )
