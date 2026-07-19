"""Unit tests for analysis-run performance telemetry foundation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from transcriptx.core.llm.metrics import RecorderBackedLlmMetricsSink
from transcriptx.core.observability.run_performance.formulas import (
    TIMING_INCONSISTENT_TOLERANCE_MS,
    derive_module_timings,
    module_used_llm,
)
from transcriptx.core.observability.run_performance.io import (
    RunPerformanceLoadStatus,
    load_run_performance,
    write_run_performance,
)
from transcriptx.core.observability.run_performance.recorder import (
    PENDING_RUN_ID,
    RecorderState,
    RunPerformanceRecorder,
    get_active_recorder,
    get_current_module_id,
)
from transcriptx.core.observability.run_performance.schema import (
    MAX_SIDECAR_BYTES,
    ExecutionStatus,
    FinalStatus,
    GroupPerformanceMeta,
    LlmAggregate,
    RunPerformanceV1,
)
from transcriptx.core.pipeline.manifest_builder import (
    build_run_results_summary,
    write_run_results_summary,
)
from transcriptx.core.pipeline.manifest_loader import load_run_results
from transcriptx.core.pipeline.module_outcomes import RUN_RESULTS_SCHEMA_VERSION


@pytest.mark.unit
def test_duration_ms_round_trip_load_run_results(tmp_path: Path) -> None:
    payload = build_run_results_summary(
        run_id="r1",
        transcript_key="tk",
        modules_enabled=["stats"],
        modules_run=["stats"],
        skipped_modules=[],
        errors=[],
        terminal_outcomes={
            "stats": {"duration_ms": 42.5, "used_cache": False},
        },
    )
    path = tmp_path / "run_results.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_run_results(path)
    row = loaded["module_outcomes"][0]
    assert row["duration_ms"] == 42.5
    assert loaded["schema_version"] == RUN_RESULTS_SCHEMA_VERSION


@pytest.mark.unit
def test_write_run_results_persists_duration_and_used_cache(tmp_path: Path) -> None:
    run_dir = tmp_path / "out"
    run_dir.mkdir()
    path = write_run_results_summary(
        run_dir=run_dir,
        run_id="run-1",
        transcript_key="tk",
        modules_enabled=["stats", "emotion"],
        modules_run=["stats"],
        skipped_modules=[],
        errors=[],
        terminal_outcomes={
            "stats": {"duration_ms": 12.5, "used_cache": True},
        },
    )
    loaded = load_run_results(path)
    by_id = {r["module_id"]: r for r in loaded["module_outcomes"]}
    assert by_id["stats"]["duration_ms"] == 12.5
    assert by_id["stats"]["used_cache"] is True


@pytest.mark.unit
def test_aborted_unreached_modules_are_blocked() -> None:
    payload = build_run_results_summary(
        run_id="r1",
        transcript_key="tk",
        modules_enabled=["stats", "emotion"],
        modules_run=["stats"],
        skipped_modules=[],
        errors=[],
        terminal_outcomes={"stats": {"duration_ms": 10.0}},
        pipeline_status="aborted",
    )
    by_id = {r["module_id"]: r for r in payload["module_outcomes"]}
    assert by_id["stats"]["execution_status"] == "run"
    assert by_id["emotion"]["execution_status"] == "blocked"
    assert by_id["emotion"]["reason_code"] == "pipeline_aborted_before_start"


@pytest.mark.unit
def test_recorder_contextvar_no_leak() -> None:
    r1 = RunPerformanceRecorder(run_id="a", target_type="transcript")
    r1.start_wall_clock()
    r1.bind()
    assert get_active_recorder() is r1
    with r1.module_scope("stats"):
        assert get_current_module_id() == "stats"
    assert get_current_module_id() is None
    r1.unbind()
    assert get_active_recorder() is None


@pytest.mark.unit
def test_recorder_freeze_is_idempotent() -> None:
    rec = RunPerformanceRecorder(run_id="run_x", target_type="transcript")
    rec.start_wall_clock()
    rec.stop_wall_clock()
    snap1 = rec.freeze(
        execution_status=ExecutionStatus.succeeded,
        final_status=FinalStatus.succeeded,
    )
    snap2 = rec.freeze(
        execution_status=ExecutionStatus.failed,
        final_status=FinalStatus.failed,
    )
    assert snap1 is snap2
    assert snap2.execution_status == ExecutionStatus.succeeded
    assert rec.state == RecorderState.frozen


@pytest.mark.unit
def test_recorder_cannot_start_twice() -> None:
    rec = RunPerformanceRecorder(run_id="run_x", target_type="transcript")
    rec.start_wall_clock()
    with pytest.raises(RuntimeError, match="cannot start"):
        rec.start_wall_clock()


@pytest.mark.unit
def test_sidecar_round_trip_and_strict_json(tmp_path: Path) -> None:
    rec = RunPerformanceRecorder(run_id="run_x", target_type="transcript")
    rec.start_wall_clock()
    rec.record_llm_call(
        success=True,
        retry_count=1,
        logical_wall_ms=12.0,
        attempt_exec_ms=10.0,
        model="m",
        effort="low",
        eval_count=10,
        eval_duration_ns=1_000_000_000,
    )
    rec.stop_wall_clock()
    snap = rec.freeze(
        execution_status=ExecutionStatus.succeeded,
        final_status=FinalStatus.succeeded,
    )
    write_run_performance(tmp_path, snap)
    loaded = load_run_performance(tmp_path, expected_run_id="run_x")
    assert loaded.status == RunPerformanceLoadStatus.ok
    assert loaded.payload is not None
    assert loaded.payload.llm is not None
    assert loaded.payload.llm.retry_count == 1
    assert loaded.payload.llm.tokens_per_second == pytest.approx(10.0)


@pytest.mark.unit
def test_load_missing_vs_malformed(tmp_path: Path) -> None:
    assert load_run_performance(tmp_path).status == RunPerformanceLoadStatus.missing
    bad = tmp_path / ".transcriptx" / "run_performance.json"
    bad.parent.mkdir(parents=True)
    bad.write_text("{not-json", encoding="utf-8")
    assert load_run_performance(tmp_path).status == RunPerformanceLoadStatus.malformed


@pytest.mark.unit
def test_load_run_id_mismatch_and_unsupported_schema(tmp_path: Path) -> None:
    snap = RunPerformanceV1(
        run_id="run_a",
        target_type="transcript",
        wall_clock_duration_ms=1.0,
        execution_status=ExecutionStatus.succeeded,
        final_status=FinalStatus.succeeded,
    )
    write_run_performance(tmp_path, snap)
    mismatch = load_run_performance(tmp_path, expected_run_id="run_b")
    assert mismatch.status == RunPerformanceLoadStatus.malformed
    assert mismatch.detail_code == "run_id_mismatch"

    path = tmp_path / ".transcriptx" / "run_performance.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 99,
                "timing_scope_version": 1,
                "run_id": "x",
                "target_type": "transcript",
                "wall_clock_duration_ms": 1.0,
                "execution_status": "succeeded",
                "final_status": "succeeded",
            }
        ),
        encoding="utf-8",
    )
    unsupported = load_run_performance(tmp_path)
    assert unsupported.status == RunPerformanceLoadStatus.unsupported_schema


@pytest.mark.unit
def test_load_oversized_sidecar(tmp_path: Path) -> None:
    path = tmp_path / ".transcriptx" / "run_performance.json"
    path.parent.mkdir(parents=True)
    # Size gate uses st_size before JSON parse; pad beyond limit.
    path.write_bytes(b"{" + (b"x" * (MAX_SIDECAR_BYTES + 1)))
    assert load_run_performance(tmp_path).status == RunPerformanceLoadStatus.oversized


@pytest.mark.unit
def test_schema_rejects_nan_negative_and_extra_keys() -> None:
    with pytest.raises(ValidationError):
        RunPerformanceV1(
            run_id="r",
            target_type="transcript",
            wall_clock_duration_ms=float("nan"),
            execution_status=ExecutionStatus.succeeded,
            final_status=FinalStatus.succeeded,
        )
    with pytest.raises(ValidationError):
        RunPerformanceV1(
            run_id="r",
            target_type="transcript",
            wall_clock_duration_ms=-1.0,
            execution_status=ExecutionStatus.succeeded,
            final_status=FinalStatus.succeeded,
        )
    with pytest.raises(ValidationError):
        RunPerformanceV1.model_validate(
            {
                "schema_version": 1,
                "timing_scope_version": 1,
                "run_id": "r",
                "target_type": "transcript",
                "wall_clock_duration_ms": 1.0,
                "execution_status": "succeeded",
                "final_status": "succeeded",
                "modules": [{"module_id": "stats", "duration_ms": 1.0}],
            }
        )
    with pytest.raises(ValidationError):
        LlmAggregate(
            call_count=1,
            success_count=1,
            failure_count=1,
            retry_count=0,
            logical_wall_ms=1.0,
        )


@pytest.mark.unit
def test_derive_timings_percent_of_cumulative() -> None:
    derived = derive_module_timings(
        module_outcomes=[
            {"module_id": "a", "execution_status": "run", "duration_ms": 75.0},
            {"module_id": "b", "execution_status": "run", "duration_ms": 25.0},
        ],
        wall_clock_duration_ms=120.0,
    )
    assert derived.module_duration_sum_ms == 100.0
    assert derived.unattributed_duration_ms == 20.0
    assert derived.rows[0].module_id == "a"
    assert derived.rows[0].pct_of_cumulative == pytest.approx(75.0)


@pytest.mark.unit
def test_derive_timings_excludes_blocked_and_skipped() -> None:
    derived = derive_module_timings(
        module_outcomes=[
            {"module_id": "a", "execution_status": "run", "duration_ms": 40.0},
            {"module_id": "b", "execution_status": "blocked", "duration_ms": 999.0},
            {"module_id": "c", "execution_status": "skipped", "duration_ms": 50.0},
            {"module_id": "d", "execution_status": "failed", "duration_ms": 10.0},
        ],
        wall_clock_duration_ms=100.0,
    )
    assert derived.module_duration_sum_ms == 50.0
    assert derived.unattributed_duration_ms == 50.0
    by_id = {r.module_id: r for r in derived.rows}
    assert by_id["b"].pct_of_cumulative is None
    assert by_id["c"].pct_of_cumulative is None
    assert by_id["d"].pct_of_cumulative == pytest.approx(20.0)


@pytest.mark.unit
def test_derive_timings_marks_inconsistent_when_sum_exceeds_wall() -> None:
    wall = 100.0
    derived = derive_module_timings(
        module_outcomes=[
            {
                "module_id": "a",
                "execution_status": "run",
                "duration_ms": wall + TIMING_INCONSISTENT_TOLERANCE_MS + 1.0,
            },
        ],
        wall_clock_duration_ms=wall,
    )
    assert derived.timing_inconsistent is True
    assert derived.unattributed_duration_ms is None


@pytest.mark.unit
def test_derive_timings_overlapping_leaves_unattributed_none() -> None:
    derived = derive_module_timings(
        module_outcomes=[
            {"module_id": "a", "execution_status": "run", "duration_ms": 40.0},
        ],
        wall_clock_duration_ms=100.0,
        concurrency_note="possibly_overlapping",
    )
    assert derived.unattributed_duration_ms is None
    assert derived.timing_inconsistent is False


@pytest.mark.unit
def test_module_used_llm_and_derive_flags() -> None:
    assert module_used_llm("stats", None) is False
    assert (
        module_used_llm(
            "stats",
            [{"module_id": "stats", "call_count": 0}],
        )
        is False
    )
    assert (
        module_used_llm(
            "stats",
            [{"module_id": "stats", "call_count": 2}],
        )
        is True
    )
    derived = derive_module_timings(
        module_outcomes=[
            {"module_id": "stats", "execution_status": "run", "duration_ms": 1.0},
            {"module_id": "emotion", "execution_status": "run", "duration_ms": 1.0},
        ],
        wall_clock_duration_ms=10.0,
        llm_by_module=[{"module_id": "stats", "call_count": 1}],
    )
    by_id = {r.module_id: r for r in derived.rows}
    assert by_id["stats"].used_llm is True
    assert by_id["emotion"].used_llm is False


@pytest.mark.unit
def test_llm_metrics_sink_forwards_only_when_recorder_bound() -> None:
    sink = RecorderBackedLlmMetricsSink()
    sink.record_generate(
        success=True,
        retry_count=0,
        logical_wall_ms=5.0,
        attempt_exec_ms=4.0,
    )
    rec = RunPerformanceRecorder(run_id="run_llm", target_type="transcript")
    rec.start_wall_clock()
    rec.bind()
    try:
        with rec.module_scope("insights"):
            sink.record_generate(
                success=True,
                retry_count=2,
                logical_wall_ms=11.0,
                attempt_exec_ms=9.0,
                model="m1",
                effort="medium",
                eval_count=20,
                eval_duration_ns=2_000_000_000,
            )
    finally:
        rec.unbind()
    rec.stop_wall_clock()
    snap = rec.freeze(
        execution_status=ExecutionStatus.succeeded,
        final_status=FinalStatus.succeeded,
    )
    assert snap.llm is not None
    assert snap.llm.call_count == 1
    assert snap.llm.retry_count == 2
    assert snap.llm.by_module[0].module_id == "insights"
    assert snap.llm.tokens_per_second == pytest.approx(10.0)


@pytest.mark.unit
def test_set_run_id_one_time_and_freeze_requires_authoritative_id() -> None:
    rec = RunPerformanceRecorder(run_id=PENDING_RUN_ID, target_type="transcript")
    rec.start_wall_clock()
    rec.stop_wall_clock()
    with pytest.raises(RuntimeError, match="authoritative run_id"):
        rec.freeze(
            execution_status=ExecutionStatus.succeeded,
            final_status=FinalStatus.succeeded,
        )
    rec.set_run_id("run_auth")
    with pytest.raises(RuntimeError, match="already assigned"):
        rec.set_run_id("run_other")
    rec.set_run_id("run_auth")  # idempotent same id
    snap = rec.freeze(
        execution_status=ExecutionStatus.succeeded,
        final_status=FinalStatus.succeeded,
    )
    assert snap.run_id == "run_auth"


@pytest.mark.unit
def test_stop_wall_clock_idempotent_after_stop() -> None:
    rec = RunPerformanceRecorder(run_id=PENDING_RUN_ID, target_type="transcript")
    rec.set_run_id("run_x")
    rec.start_wall_clock()
    first = rec.stop_wall_clock()
    second = rec.stop_wall_clock()
    assert first == second
    assert rec.state == RecorderState.stopped


@pytest.mark.unit
def test_group_sidecar_round_trip_and_expected_target_type(tmp_path: Path) -> None:
    rec = RunPerformanceRecorder(run_id=PENDING_RUN_ID, target_type="group")
    rec.set_run_id("group_run_1")
    rec.start_wall_clock()
    rec.stop_wall_clock()
    snap = rec.freeze(
        execution_status=ExecutionStatus.partial,
        final_status=FinalStatus.partial,
        group=GroupPerformanceMeta(
            member_count=2,
            members_completed=1,
            members_failed=1,
            partial=True,
        ),
    )
    assert snap.llm is None
    write_run_performance(tmp_path, snap)
    loaded = load_run_performance(
        tmp_path, expected_run_id="group_run_1", expected_target_type="group"
    )
    assert loaded.status == RunPerformanceLoadStatus.ok
    assert loaded.payload is not None
    assert loaded.payload.target_type == "group"
    assert loaded.payload.group is not None
    assert loaded.payload.group.member_count == 2

    mismatch = load_run_performance(tmp_path, expected_target_type="transcript")
    assert mismatch.status == RunPerformanceLoadStatus.malformed
    assert mismatch.detail_code == "target_type_mismatch"


@pytest.mark.unit
def test_schema_group_meta_required_and_forbidden_on_transcript() -> None:
    with pytest.raises(ValidationError, match="group metadata required"):
        RunPerformanceV1(
            run_id="r",
            target_type="group",
            wall_clock_duration_ms=1.0,
            execution_status=ExecutionStatus.succeeded,
            final_status=FinalStatus.succeeded,
        )
    with pytest.raises(ValidationError, match="group metadata forbidden"):
        RunPerformanceV1(
            run_id="r",
            target_type="transcript",
            wall_clock_duration_ms=1.0,
            execution_status=ExecutionStatus.succeeded,
            final_status=FinalStatus.succeeded,
            group=GroupPerformanceMeta(member_count=1),
        )
