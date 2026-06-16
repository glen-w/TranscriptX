"""Finalization phase helpers for DAG pipeline execution."""

from __future__ import annotations

import time
from typing import Any, Dict, List


def finalize_execution_results(
    *,
    results: Dict[str, Any],
    execution_order: List[str],
    aborted: bool,
    setup_failed: bool,
    total_modules: int,
    ev_completed: int,
    ev_skipped: int,
    ev_failed: int,
    emit,
    abort_error: str | None = None,
    setup_error: str | None = None,
) -> Dict[str, Any]:
    """Finalize result payload and emit exactly one terminal run event."""
    results["end_time"] = time.time()
    results["duration"] = results["end_time"] - results["start_time"]
    if "execution_order" not in results:
        results["execution_order"] = execution_order

    terminal_event = "run_completed"
    message = f"Pipeline complete: {ev_completed} run, {ev_skipped} skipped, {ev_failed} failed"
    error_payload = None
    if setup_failed:
        terminal_event = "run_failed"
        error_payload = setup_error
        message = "Pipeline failed during setup"
    elif aborted:
        terminal_event = "run_failed"
        error_payload = abort_error
        message = "Pipeline aborted"

    try:
        emit(
            {
                "event": terminal_event,
                "total": total_modules,
                "completed": ev_completed,
                "skipped": ev_skipped,
                "failed": ev_failed,
                "pct": 100.0,
                "message": message,
                "error": error_payload,
            }
        )
    except Exception:
        # Best-effort by contract: sink failures must not break result finalization.
        pass
    return results
