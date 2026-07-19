"""Assemble analysis-run performance view models (presentation helpers stay in the page)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from transcriptx.core.observability.run_performance.formulas import (
    DerivedRunTiming,
    derive_module_timings,
)
from transcriptx.core.observability.run_performance.io import (
    RunPerformanceLoadStatus,
    load_run_performance,
)
from transcriptx.core.pipeline.manifest_loader import load_run_results


@dataclass(frozen=True)
class RunPerformanceViewModel:
    run_results: Optional[dict[str, Any]]
    performance_status: RunPerformanceLoadStatus
    performance_detail: Optional[str]
    wall_clock_duration_ms: Optional[float]
    derived: DerivedRunTiming
    llm: Optional[dict[str, Any]]
    provenance_notes: tuple[str, ...]


def build_run_performance_view(run_root: Path) -> RunPerformanceViewModel:
    notes: list[str] = []
    run_results: Optional[dict[str, Any]] = None
    try:
        run_results = load_run_results(run_root / "run_results.json")
    except Exception:
        notes.append("run_results unavailable or invalid")

    expected_run_id = None
    if run_results:
        expected_run_id = str(run_results.get("run_id") or "") or None
    loaded = load_run_performance(run_root, expected_run_id=expected_run_id)
    if loaded.status == RunPerformanceLoadStatus.missing:
        notes.append(
            "No run_performance.json (old run or telemetry not written). "
            "Module timings use run_results when present."
        )
    elif loaded.status != RunPerformanceLoadStatus.ok:
        notes.append(f"Performance sidecar status: {loaded.status.value}")

    wall = None
    llm = None
    if loaded.payload is not None:
        wall = loaded.payload.wall_clock_duration_ms
        if loaded.payload.llm is not None:
            llm = loaded.payload.llm.model_dump(mode="json")

    outcomes = []
    if run_results and isinstance(run_results.get("module_outcomes"), list):
        outcomes = list(run_results["module_outcomes"])

    llm_by_module = None
    if llm and isinstance(llm.get("by_module"), list):
        llm_by_module = llm["by_module"]

    derived = derive_module_timings(
        module_outcomes=outcomes,
        wall_clock_duration_ms=wall,
        llm_by_module=llm_by_module,
    )
    if derived.timing_inconsistent:
        notes.append(
            "timing_inconsistent: cumulative module time exceeds wall clock "
            "beyond tolerance (not clamped)."
        )

    return RunPerformanceViewModel(
        run_results=run_results,
        performance_status=loaded.status,
        performance_detail=loaded.detail_code,
        wall_clock_duration_ms=wall,
        derived=derived,
        llm=llm,
        provenance_notes=tuple(notes),
    )
