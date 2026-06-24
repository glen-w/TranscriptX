"""Pure helpers for DAG pipeline progress percentages and structured run events."""

from __future__ import annotations

from typing import Any, Dict


def progress_pct(completed: int, skipped: int, failed: int, total: int) -> float:
    if not total:
        return 0.0
    return (completed + skipped + failed) / total * 100.0


def _progress_fields(
    completed: int, skipped: int, failed: int, total: int
) -> Dict[str, Any]:
    return {
        "completed": completed,
        "skipped": skipped,
        "failed": failed,
        "total": total,
        "pct": progress_pct(completed, skipped, failed, total),
    }


def run_started_event(*, total_modules: int) -> Dict[str, Any]:
    return {
        "event": "run_started",
        "total": total_modules,
        "message": f"Starting pipeline: {total_modules} modules",
    }


def module_started_event(
    *,
    module_name: str,
    index: int,
    total_modules: int,
    ev_completed: int,
    ev_skipped: int,
    ev_failed: int,
) -> Dict[str, Any]:
    return {
        "event": "module_started",
        "module_name": module_name,
        "index": index,
        **_progress_fields(ev_completed, ev_skipped, ev_failed, total_modules),
    }


def module_skipped_event(
    *,
    module_name: str,
    index: int,
    total_modules: int,
    ev_completed: int,
    ev_skipped: int,
    ev_failed: int,
    message: str,
) -> Dict[str, Any]:
    return {
        "event": "module_skipped",
        "module_name": module_name,
        "index": index,
        **_progress_fields(ev_completed, ev_skipped, ev_failed, total_modules),
        "message": message,
    }


def module_completed_event(
    *,
    module_name: str,
    index: int,
    total_modules: int,
    ev_completed: int,
    ev_skipped: int,
    ev_failed: int,
    duration_ms: float,
) -> Dict[str, Any]:
    return {
        "event": "module_completed",
        "module_name": module_name,
        "index": index,
        **_progress_fields(ev_completed, ev_skipped, ev_failed, total_modules),
        "duration_ms": duration_ms,
    }


def module_failed_event(
    *,
    module_name: str,
    index: int,
    total_modules: int,
    ev_completed: int,
    ev_skipped: int,
    ev_failed: int,
    error: str | None,
    error_code: str | None = None,
) -> Dict[str, Any]:
    event: Dict[str, Any] = {
        "event": "module_failed",
        "module_name": module_name,
        "index": index,
        **_progress_fields(ev_completed, ev_skipped, ev_failed, total_modules),
        "error": error,
    }
    if error_code:
        event["error_code"] = error_code
    return event


def run_failed_event(
    *,
    total_modules: int,
    ev_completed: int,
    ev_skipped: int,
    ev_failed: int,
    error: str | None,
    message: str,
) -> Dict[str, Any]:
    return {
        "event": "run_failed",
        "error": error,
        "total": total_modules,
        "completed": ev_completed,
        "skipped": ev_skipped,
        "failed": ev_failed,
        "message": message,
    }
