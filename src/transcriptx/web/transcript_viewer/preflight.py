"""Preflight resolution for transcript viewer context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Mapping

from transcriptx.web.transcript_view_state import (
    TranscriptViewerContextResult,
    transcript_context_result,
)


@dataclass(frozen=True)
class ViewerPreflight:
    status: Literal[
        "ok", "no_subject", "group_browser", "wrong_subject", "no_run", "context_failed"
    ]
    subject: Any | None = None
    run_id: str | None = None
    context_result: TranscriptViewerContextResult | None = None


def resolve_viewer_preflight(
    session_state: Mapping[str, Any],
    *,
    resolve_subject: Callable[[Mapping[str, Any]], Any | None],
    get_run_root: Callable[[str, str, str | None], Path],
) -> ViewerPreflight:
    """Resolve subject/run context for transcript page rendering."""
    subject = resolve_subject(session_state)
    run_id = session_state.get("run_id")
    if not subject:
        return ViewerPreflight(
            status="no_subject",
            subject=subject,
            run_id=run_id,
            context_result=transcript_context_result(ok=False, reason="uninitialized"),
        )
    if getattr(subject, "subject_type", None) == "group":
        return ViewerPreflight(status="group_browser", subject=subject, run_id=run_id)
    if getattr(subject, "subject_type", None) != "transcript":
        return ViewerPreflight(status="wrong_subject", subject=subject, run_id=run_id)
    if not run_id:
        return ViewerPreflight(status="no_run", subject=subject, run_id=run_id)
    run_root = get_run_root(subject.scope, run_id, subject.subject_id)
    context = transcript_context_result(
        ok=True,
        session_slug=subject.subject_id,
        run_id=run_id,
        run_root=run_root,
    )
    if not context.ok or not context.selected_session:
        return ViewerPreflight(
            status="context_failed",
            subject=subject,
            run_id=run_id,
            context_result=context,
        )
    return ViewerPreflight(
        status="ok",
        subject=subject,
        run_id=run_id,
        context_result=context,
    )
