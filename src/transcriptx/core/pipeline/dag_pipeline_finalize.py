"""Finalization phase helpers for DAG pipeline execution."""

from __future__ import annotations

import time
from typing import Any, Dict, List

from transcriptx.core.pipeline.module_registry import canonical_module_id


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
    # start_time is perf_counter; keep the same clock for elapsed duration.
    results["end_time"] = time.perf_counter()
    results["duration"] = float(results["end_time"]) - float(results["start_time"])
    if "execution_order" not in results:
        results["execution_order"] = execution_order

    if aborted:
        results["status"] = "aborted"
        reached = (
            {canonical_module_id(m) for m in results.get("modules_run", [])}
            | {
                canonical_module_id(str(e.get("module", "")))
                for e in results.get("skipped_modules", [])
                if isinstance(e, dict) and e.get("module")
            }
            | {
                canonical_module_id(str(k))
                for k in (results.get("terminal_outcomes") or {})
            }
        )
        for module_name in execution_order:
            cid = canonical_module_id(module_name)
            if cid in reached:
                continue
            results.setdefault("skipped_modules", []).append(
                {
                    "module": module_name,
                    "reason": "pipeline_aborted_before_start",
                    "execution_status": "blocked",
                }
            )
            reached.add(cid)

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
