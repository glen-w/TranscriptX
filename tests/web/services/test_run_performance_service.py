"""Unit tests for run performance view-model assembly."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.observability.run_performance.io import (
    RunPerformanceLoadStatus,
    write_run_performance,
)
from transcriptx.core.observability.run_performance.schema import (
    ExecutionStatus,
    FinalStatus,
    LlmAggregate,
    LlmByModule,
    RunPerformanceV1,
)
from transcriptx.core.pipeline.manifest_builder import write_run_results_summary
from transcriptx.web.services.run_performance_service import build_run_performance_view


@pytest.mark.unit
def test_build_view_missing_sidecar_still_derives_from_run_results(
    tmp_path: Path,
) -> None:
    write_run_results_summary(
        run_dir=tmp_path,
        run_id="run-1",
        transcript_key="tk",
        modules_enabled=["stats", "emotion"],
        modules_run=["stats"],
        skipped_modules=[],
        errors=[],
        terminal_outcomes={"stats": {"duration_ms": 40.0}},
    )
    view = build_run_performance_view(tmp_path)
    assert view.performance_status == RunPerformanceLoadStatus.missing
    assert view.wall_clock_duration_ms is None
    assert view.derived.module_duration_sum_ms == 40.0
    assert any("No run_performance.json" in n for n in view.provenance_notes)


@pytest.mark.unit
def test_build_view_joins_sidecar_wall_and_llm(tmp_path: Path) -> None:
    write_run_results_summary(
        run_dir=tmp_path,
        run_id="run-2",
        transcript_key="tk",
        modules_enabled=["stats", "insights"],
        modules_run=["stats", "insights"],
        skipped_modules=[],
        errors=[],
        terminal_outcomes={
            "stats": {"duration_ms": 30.0},
            "insights": {"duration_ms": 70.0},
        },
    )
    write_run_performance(
        tmp_path,
        RunPerformanceV1(
            run_id="run-2",
            target_type="transcript",
            wall_clock_duration_ms=120.0,
            execution_status=ExecutionStatus.succeeded,
            final_status=FinalStatus.succeeded,
            llm=LlmAggregate(
                call_count=1,
                success_count=1,
                failure_count=0,
                retry_count=0,
                logical_wall_ms=50.0,
                by_module=[
                    LlmByModule(
                        module_id="insights",
                        call_count=1,
                        success_count=1,
                        failure_count=0,
                        retry_count=0,
                        logical_wall_ms=50.0,
                    )
                ],
            ),
        ),
    )
    view = build_run_performance_view(tmp_path)
    assert view.performance_status == RunPerformanceLoadStatus.ok
    assert view.wall_clock_duration_ms == 120.0
    assert view.derived.module_duration_sum_ms == 100.0
    assert view.derived.unattributed_duration_ms == 20.0
    by_id = {r.module_id: r for r in view.derived.rows}
    assert by_id["insights"].used_llm is True
    assert by_id["stats"].used_llm is False
    assert view.llm is not None
    assert view.llm["call_count"] == 1


@pytest.mark.unit
def test_build_view_run_id_mismatch_notes_malformed(tmp_path: Path) -> None:
    write_run_results_summary(
        run_dir=tmp_path,
        run_id="expected",
        transcript_key="tk",
        modules_enabled=["stats"],
        modules_run=["stats"],
        skipped_modules=[],
        errors=[],
        terminal_outcomes={"stats": {"duration_ms": 5.0}},
    )
    write_run_performance(
        tmp_path,
        RunPerformanceV1(
            run_id="other",
            target_type="transcript",
            wall_clock_duration_ms=10.0,
            execution_status=ExecutionStatus.succeeded,
            final_status=FinalStatus.succeeded,
        ),
    )
    view = build_run_performance_view(tmp_path)
    assert view.performance_status == RunPerformanceLoadStatus.malformed
    assert view.performance_detail == "run_id_mismatch"
    assert view.wall_clock_duration_ms is None
    assert any("malformed" in n for n in view.provenance_notes)


@pytest.mark.unit
def test_build_view_invalid_run_results_notes_unavailable(tmp_path: Path) -> None:
    (tmp_path / "run_results.json").write_text("{not-json", encoding="utf-8")
    view = build_run_performance_view(tmp_path)
    assert view.run_results is None
    assert any("run_results unavailable" in n for n in view.provenance_notes)
    assert view.derived.module_duration_sum_ms is None
