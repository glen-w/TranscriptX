from __future__ import annotations

from transcriptx.core.pipeline.contracts import ErrorKind, PersistenceOutcome
from transcriptx.core.pipeline.run_orchestrator import RunOrchestrator, _combine_status


def test_combine_status_returns_failed_on_required_failure_even_when_succeeded() -> (
    None
):
    outcomes = [
        PersistenceOutcome(
            name="run_results",
            success=False,
            severity="required",
            error_kind=ErrorKind.PERSISTENCE,
            error_message="disk full",
        )
    ]
    assert _combine_status("succeeded", outcomes) == "failed"


def test_combine_status_preserves_aborted_without_required_failures() -> None:
    outcomes = [PersistenceOutcome(name="manifest", success=True, severity="required")]
    assert _combine_status("aborted", outcomes) == "aborted"


def test_emit_terminal_event_best_effort_ignores_sink_exceptions() -> None:
    orchestrator = RunOrchestrator()

    def _boom(_event: dict) -> None:
        raise RuntimeError("sink failed")

    # No exception should escape.
    orchestrator._emit_terminal_event_best_effort(
        on_event=_boom,
        event="run_failed",
        message="Pipeline failed",
        error="boom",
    )


def test_emit_terminal_event_best_effort_payload_shape() -> None:
    orchestrator = RunOrchestrator()
    events: list[dict] = []
    orchestrator._emit_terminal_event_best_effort(
        on_event=lambda event: events.append(event),
        event="run_failed",
        message="Pipeline failed during setup",
        error="setup",
    )
    assert len(events) == 1
    assert events[0]["event"] == "run_failed"
    assert events[0]["pct"] == 100.0
    assert events[0]["failed"] == 1
    assert events[0]["error"] == "setup"
