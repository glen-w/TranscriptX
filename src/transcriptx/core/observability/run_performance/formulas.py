"""Read-time formulas for analysis-run performance views."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

TIMING_INCONSISTENT_TOLERANCE_MS = 25.0


@dataclass(frozen=True)
class ModuleTimingRow:
    module_id: str
    status: str
    duration_ms: Optional[float]
    used_cache: bool
    used_llm: bool
    pct_of_cumulative: Optional[float]


@dataclass(frozen=True)
class DerivedRunTiming:
    module_duration_sum_ms: Optional[float]
    unattributed_duration_ms: Optional[float]
    timing_inconsistent: bool
    rows: List[ModuleTimingRow]


def module_used_llm(
    module_id: str, llm_by_module: Sequence[Dict[str, Any]] | None
) -> bool:
    if not llm_by_module:
        return False
    for row in llm_by_module:
        if row.get("module_id") == module_id and int(row.get("call_count") or 0) > 0:
            return True
    return False


def derive_module_timings(
    *,
    module_outcomes: Sequence[Dict[str, Any]],
    wall_clock_duration_ms: Optional[float],
    concurrency_note: str = "sequential",
    llm_by_module: Sequence[Dict[str, Any]] | None = None,
) -> DerivedRunTiming:
    """Cumulative = sum of non-null durations for run/failed rows that started."""
    rows_out: List[ModuleTimingRow] = []
    timed: List[float] = []
    for raw in module_outcomes:
        mid = str(raw.get("module_id") or "")
        status = str(raw.get("execution_status") or raw.get("status") or "")
        dur = raw.get("duration_ms")
        duration_ms: Optional[float]
        if dur is None:
            duration_ms = None
        else:
            try:
                duration_ms = float(dur)
            except (TypeError, ValueError):
                duration_ms = None
        # Count executed/failed timings (started). run == succeeded in write-side vocab.
        if duration_ms is not None and status in {"run", "succeeded", "failed"}:
            timed.append(duration_ms)
        rows_out.append(
            ModuleTimingRow(
                module_id=mid,
                status=status,
                duration_ms=duration_ms,
                used_cache=bool(raw.get("used_cache")),
                used_llm=module_used_llm(mid, llm_by_module),
                pct_of_cumulative=None,
            )
        )

    total = sum(timed) if timed else None
    if total and total > 0:
        rows_out = [
            ModuleTimingRow(
                module_id=r.module_id,
                status=r.status,
                duration_ms=r.duration_ms,
                used_cache=r.used_cache,
                used_llm=r.used_llm,
                pct_of_cumulative=(
                    (100.0 * r.duration_ms / total)
                    if r.duration_ms is not None
                    and r.status in {"run", "succeeded", "failed"}
                    else None
                ),
            )
            for r in rows_out
        ]

    unattributed: Optional[float] = None
    inconsistent = False
    if (
        wall_clock_duration_ms is not None
        and total is not None
        and concurrency_note == "sequential"
    ):
        delta = wall_clock_duration_ms - total
        if delta < -TIMING_INCONSISTENT_TOLERANCE_MS:
            inconsistent = True
            unattributed = None
        else:
            unattributed = max(0.0, delta)
    elif concurrency_note == "possibly_overlapping":
        unattributed = None

    return DerivedRunTiming(
        module_duration_sum_ms=total,
        unattributed_duration_ms=unattributed,
        timing_inconsistent=inconsistent,
        rows=sorted(
            rows_out,
            key=lambda r: (
                -(r.duration_ms if r.duration_ms is not None else -1.0),
                r.module_id,
            ),
        ),
    )
