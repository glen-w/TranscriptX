"""Finalization phase helpers for DAG pipeline execution."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from transcriptx.core.pipeline.dag_pipeline_progress import (
    run_completed_event,
    run_failed_event,
)
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
    pending_finalize_modules: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Finalize result payload and emit the DAG-phase terminal progress event.

    When ``pending_finalize_modules`` is non-empty and the DAG succeeded, defer
    ``run_completed`` so persistence can report finalize-phase modules
    (e.g. ``chart_descriptions``) before the UI flips to Completed.
    """
    # start_time is perf_counter; keep the same clock for elapsed duration.
    results["end_time"] = time.perf_counter()
    results["duration"] = float(results["end_time"]) - float(results["start_time"])
    if "execution_order" not in results:
        results["execution_order"] = execution_order

    pending = [str(m) for m in (pending_finalize_modules or []) if str(m).strip()]
    results["pending_finalize_modules"] = list(pending)
    results["progress_counts"] = {
        "completed": int(ev_completed),
        "skipped": int(ev_skipped),
        "failed": int(ev_failed),
        "total": int(total_modules),
    }

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

    defer_terminal = bool(pending) and not setup_failed and not aborted
    results["defer_run_completed"] = defer_terminal
    if defer_terminal:
        # Persistence emits finalize-module progress + run_completed.
        return results

    message = f"Pipeline complete: {ev_completed} run, {ev_skipped} skipped, {ev_failed} failed"
    try:
        if setup_failed:
            emit(
                run_failed_event(
                    total_modules=total_modules,
                    ev_completed=ev_completed,
                    ev_skipped=ev_skipped,
                    ev_failed=ev_failed,
                    error=setup_error,
                    message="Pipeline failed during setup",
                )
            )
        elif aborted:
            emit(
                run_failed_event(
                    total_modules=total_modules,
                    ev_completed=ev_completed,
                    ev_skipped=ev_skipped,
                    ev_failed=ev_failed,
                    error=abort_error,
                    message="Pipeline aborted",
                )
            )
        else:
            emit(
                run_completed_event(
                    total_modules=total_modules,
                    ev_completed=ev_completed,
                    ev_skipped=ev_skipped,
                    ev_failed=ev_failed,
                    message=message,
                )
            )
    except Exception:
        # Best-effort by contract: sink failures must not break result finalization.
        pass
    return results
