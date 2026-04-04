"""Lightweight in-process metrics for Corrections Studio (Phase 7 observability hook)."""

from __future__ import annotations

from typing import Any, Dict

_counters: Dict[str, int] = {
    "sessions_started": 0,
    "candidates_generated": 0,
    "reviews_recorded": 0,
    "previews_computed": 0,
    "exports_completed": 0,
}


def increment(metric: str, delta: int = 1) -> None:
    _counters[metric] = _counters.get(metric, 0) + delta


def snapshot() -> Dict[str, Any]:
    return dict(_counters)
