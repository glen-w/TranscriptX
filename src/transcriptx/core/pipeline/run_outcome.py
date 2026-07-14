"""Combine run status and emit terminal pipeline events."""

from __future__ import annotations

from typing import Any, List, Optional

from transcriptx.core.pipeline.contracts import PersistenceOutcome, RunStatus


def combine_status(
    execution_status: RunStatus, persistence_outcomes: List[PersistenceOutcome]
) -> RunStatus:
    required_failure = any(
        (not outcome.success) and outcome.severity == "required"
        for outcome in persistence_outcomes
    )
    optional_failure = any(
        (not outcome.success) and outcome.severity == "optional"
        for outcome in persistence_outcomes
    )
    if execution_status == "aborted" and required_failure:
        return "failed"
    if required_failure:
        return "failed"
    if execution_status in {"failed", "aborted"}:
        return execution_status
    if optional_failure and execution_status == "succeeded":
        return "partial"
    return execution_status


def emit_terminal_event_best_effort(
    *,
    on_event: Optional[Any],
    event: str,
    message: str,
    error: Optional[str] = None,
) -> None:
    if on_event is None:
        return
    try:
        on_event(
            {
                "event": event,
                "total": 0,
                "completed": 0,
                "skipped": 0,
                "failed": 1,
                "pct": 100.0,
                "message": message,
                "error": error,
            }
        )
    except Exception:
        # Best-effort by contract.
        pass
