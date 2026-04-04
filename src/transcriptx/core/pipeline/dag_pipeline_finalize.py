"""Finalization phase helpers for DAG pipeline execution."""

from __future__ import annotations

import time
from typing import Any, Dict, List


def finalize_execution_results(
    *,
    results: Dict[str, Any],
    execution_order: List[str],
    aborted: bool,
    total_modules: int,
    ev_completed: int,
    ev_skipped: int,
    ev_failed: int,
    emit,
) -> Dict[str, Any]:
    """Finalize result payload and emit terminal run event when applicable."""
    results["end_time"] = time.time()
    results["duration"] = results["end_time"] - results["start_time"]
    if "execution_order" not in results:
        results["execution_order"] = execution_order

    if not aborted:
        has_errors = bool(results.get("errors"))
        emit(
            {
                "event": "run_completed" if not has_errors else "run_completed",
                "total": total_modules,
                "completed": ev_completed,
                "skipped": ev_skipped,
                "failed": ev_failed,
                "pct": 100.0,
                "message": (
                    f"Pipeline complete: {ev_completed} run, {ev_skipped} skipped, {ev_failed} failed"
                ),
            }
        )
    return results
