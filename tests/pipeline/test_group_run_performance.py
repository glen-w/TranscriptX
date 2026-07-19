"""Group finalize → run_performance.json sidecar (aggregation-disabled path)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from transcriptx.core.observability.run_performance.io import (
    RunPerformanceLoadStatus,
    load_run_performance,
)
from transcriptx.core.observability.run_performance.recorder import (
    PENDING_RUN_ID,
    RecorderState,
    RunPerformanceRecorder,
    get_active_recorder,
)
from transcriptx.core.pipeline.group_analysis_runner import (
    PERFORMANCE_SIDECAR_RESULTS_UNAVAILABLE,
    PERFORMANCE_SIDECAR_WRITE_FAILED,
    _build_group_performance_meta,
    _derive_group_performance_statuses,
    _write_group_performance_sidecar_under_lease,
    finalize_group_analysis,
)
from transcriptx.core.pipeline.manifest_builder import build_output_manifest
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.target_resolver import AnalysisScope
from transcriptx.core.utils.config import TranscriptXConfig


def _scope() -> AnalysisScope:
    return AnalysisScope(
        scope_type="group",
        uuid="group-uuid-perf",
        key="group-key-perf",
        display_name="Perf Group",
    )


def _member() -> SimpleNamespace:
    return SimpleNamespace(
        file_path="/tmp/a.json",
        file_name="a.json",
        id=1,
        uuid="member-uuid-1",
    )


def _per_result(*, completed: bool = True) -> PerTranscriptResult:
    return PerTranscriptResult(
        transcript_path="/tmp/a.json",
        transcript_key="tx",
        run_id="mem-run-1" if completed else "",
        order_index=0,
        output_dir="/tmp/out" if completed else "",
        module_results={},
        modules_run=["stats"],
        skipped_modules=[],
    )


@pytest.mark.unit
def test_finalize_disabled_writes_group_performance_sidecar(tmp_path: Path) -> None:
    config = TranscriptXConfig()
    config.group_analysis.enabled = False
    config.group_analysis.output_dir = str(tmp_path / "groups")

    recorder = RunPerformanceRecorder(run_id=PENDING_RUN_ID, target_type="group")
    recorder.start_wall_clock()

    result = finalize_group_analysis(
        scope=_scope(),
        members=[_member()],
        resolved_paths=["/tmp/a.json"],
        per_transcript_results=[_per_result()],
        group_errors=[],
        selected_modules=["stats"],
        config=config,
        performance_recorder=recorder,
    )

    assert result["status"] == "completed"
    run_dir = Path(result["group_output_dir"])
    assert (run_dir / "run_results.json").exists()
    loaded = load_run_performance(
        run_dir,
        expected_run_id=result["group_run_id"],
        expected_target_type="group",
    )
    assert loaded.status == RunPerformanceLoadStatus.ok
    assert loaded.payload is not None
    assert loaded.payload.target_type == "group"
    assert loaded.payload.run_id == result["group_run_id"]
    assert loaded.payload.group is not None
    assert loaded.payload.group.member_count == 1
    assert loaded.payload.group.members_completed == 1
    assert loaded.payload.group.partial is False
    assert loaded.payload.wall_clock_duration_ms >= 0
    assert loaded.payload.llm is None
    assert recorder.state == RecorderState.persisted

    # Sidecar is not a user-visible manifest artifact.
    manifest = build_output_manifest(
        run_dir=run_dir,
        run_id=result["group_run_id"],
        transcript_key="group-uuid-perf",
        modules_enabled=["stats"],
    )
    rels = {a.get("rel_path") for a in manifest.get("artifacts") or []}
    assert ".transcriptx/run_performance.json" not in rels


@pytest.mark.unit
def test_finalize_disabled_partial_members_sets_partial_meta(tmp_path: Path) -> None:
    config = TranscriptXConfig()
    config.group_analysis.enabled = False
    config.group_analysis.output_dir = str(tmp_path / "groups")
    recorder = RunPerformanceRecorder(run_id=PENDING_RUN_ID, target_type="group")
    recorder.start_wall_clock()
    members = [
        SimpleNamespace(file_path="/tmp/a.json", file_name="a.json", id=1, uuid="m1"),
        SimpleNamespace(file_path="/tmp/b.json", file_name="b.json", id=2, uuid="m2"),
    ]
    results = [
        PerTranscriptResult(
            transcript_path="/tmp/a.json",
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir="/o1",
            module_results={},
            modules_run=["stats"],
            skipped_modules=[],
        ),
        PerTranscriptResult(
            transcript_path="/tmp/b.json",
            transcript_key="b",
            run_id="",
            order_index=1,
            output_dir="",
            module_results={},
            modules_run=[],
            skipped_modules=[],
        ),
    ]
    result = finalize_group_analysis(
        scope=_scope(),
        members=members,
        resolved_paths=["/tmp/a.json", "/tmp/b.json"],
        per_transcript_results=results,
        group_errors=["member b failed"],
        selected_modules=["stats"],
        config=config,
        performance_recorder=recorder,
    )
    loaded = load_run_performance(Path(result["group_output_dir"]))
    assert loaded.payload is not None
    assert loaded.payload.group is not None
    assert loaded.payload.group.partial is True
    assert loaded.payload.group.members_completed == 1
    assert loaded.payload.group.members_failed == 1
    assert loaded.payload.execution_status.value == "partial"


@pytest.mark.unit
def test_sidecar_skipped_when_run_results_missing(tmp_path: Path) -> None:
    recorder = RunPerformanceRecorder(run_id=PENDING_RUN_ID, target_type="group")
    recorder.set_run_id("g1")
    recorder.start_wall_clock()
    warning = _write_group_performance_sidecar_under_lease(
        run_dir=tmp_path,
        performance_recorder=recorder,
        per_transcript_results=[_per_result()],
        group_errors=[],
        selected_modules=["stats"],
        aggregation_disabled=True,
    )
    assert warning == PERFORMANCE_SIDECAR_RESULTS_UNAVAILABLE
    assert not (tmp_path / ".transcriptx" / "run_performance.json").exists()
    assert recorder.state == RecorderState.stopped


@pytest.mark.unit
def test_sidecar_skipped_when_run_results_malformed(tmp_path: Path) -> None:
    recorder = RunPerformanceRecorder(run_id=PENDING_RUN_ID, target_type="group")
    recorder.set_run_id("g1")
    recorder.start_wall_clock()
    (tmp_path / "run_results.json").write_text("{not-json", encoding="utf-8")
    warning = _write_group_performance_sidecar_under_lease(
        run_dir=tmp_path,
        performance_recorder=recorder,
        per_transcript_results=[_per_result()],
        group_errors=[],
        selected_modules=["stats"],
        aggregation_disabled=True,
    )
    assert warning == PERFORMANCE_SIDECAR_RESULTS_UNAVAILABLE
    assert recorder.state == RecorderState.stopped
    assert not (tmp_path / ".transcriptx" / "run_performance.json").exists()


@pytest.mark.unit
def test_sidecar_write_failure_is_optional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "g1",
                "transcript_key": "gk",
                "modules_enabled": ["stats"],
                "modules_run": ["stats"],
                "modules_skipped": [],
                "modules_failed": [],
                "module_outcomes": [],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    recorder = RunPerformanceRecorder(run_id=PENDING_RUN_ID, target_type="group")
    recorder.set_run_id("g1")
    recorder.start_wall_clock()

    def boom(*_a: Any, **_k: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(
        "transcriptx.core.observability.run_performance.io.write_run_performance",
        boom,
    )

    warning = _write_group_performance_sidecar_under_lease(
        run_dir=run_dir,
        performance_recorder=recorder,
        per_transcript_results=[_per_result()],
        group_errors=[],
        selected_modules=["stats"],
        aggregation_disabled=True,
    )
    assert warning == PERFORMANCE_SIDECAR_WRITE_FAILED
    assert recorder.state == RecorderState.persist_failed


@pytest.mark.unit
def test_finalize_surfaces_sidecar_write_failure_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = TranscriptXConfig()
    config.group_analysis.enabled = False
    config.group_analysis.output_dir = str(tmp_path / "groups")
    recorder = RunPerformanceRecorder(run_id=PENDING_RUN_ID, target_type="group")
    recorder.start_wall_clock()

    def boom(*_a: Any, **_k: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(
        "transcriptx.core.observability.run_performance.io.write_run_performance",
        boom,
    )
    result = finalize_group_analysis(
        scope=_scope(),
        members=[_member()],
        resolved_paths=["/tmp/a.json"],
        per_transcript_results=[_per_result()],
        group_errors=[],
        selected_modules=["stats"],
        config=config,
        performance_recorder=recorder,
    )
    assert result["status"] == "completed"
    assert (
        result["group_phase_metadata"]["performance_sidecar_warning"]
        == PERFORMANCE_SIDECAR_WRITE_FAILED
    )
    assert (Path(result["group_output_dir"]) / "run_results.json").exists()
    assert not (
        Path(result["group_output_dir"]) / ".transcriptx" / "run_performance.json"
    ).exists()


@pytest.mark.unit
def test_finalize_enabled_writes_group_performance_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = TranscriptXConfig()
    config.group_analysis.enabled = True
    config.group_analysis.output_dir = str(tmp_path / "groups")

    monkeypatch.setattr(
        "transcriptx.core.analysis.aggregation.registry.build_registry",
        lambda: [],
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.speaker_normalizer.normalize_speakers_across_transcripts",
        lambda _results: SimpleNamespace(
            transcript_to_speakers={},
            canonical_to_display={},
        ),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.group_llm_synthesis.finalize_hook.run_synthesis_publish_and_manifest",
        lambda **_kwargs: {},
    )

    recorder = RunPerformanceRecorder(run_id=PENDING_RUN_ID, target_type="group")
    recorder.start_wall_clock()
    result = finalize_group_analysis(
        scope=_scope(),
        members=[_member()],
        resolved_paths=["/tmp/a.json"],
        per_transcript_results=[_per_result()],
        group_errors=[],
        selected_modules=["stats"],
        config=config,
        performance_recorder=recorder,
    )
    assert result["status"] == "completed"
    loaded = load_run_performance(
        Path(result["group_output_dir"]),
        expected_run_id=result["group_run_id"],
        expected_target_type="group",
    )
    assert loaded.status == RunPerformanceLoadStatus.ok
    assert loaded.payload is not None
    assert loaded.payload.target_type == "group"
    assert loaded.payload.termination_reason_code is None


@pytest.mark.unit
def test_sidecar_helper_does_not_acquire_nested_run_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "g1",
                "transcript_key": "gk",
                "modules_enabled": ["stats"],
                "modules_run": ["stats"],
                "modules_skipped": [],
                "modules_failed": [],
                "module_outcomes": [],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    recorder = RunPerformanceRecorder(run_id=PENDING_RUN_ID, target_type="group")
    recorder.set_run_id("g1")
    recorder.start_wall_clock()

    def forbid_lock(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("sidecar helper must not acquire a nested per-run lock")

    monkeypatch.setattr(
        "transcriptx.core.utils.run_writer_locks.RunWriterLock.acquire",
        forbid_lock,
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.run_writer_locks.per_run_lock",
        forbid_lock,
    )

    warning = _write_group_performance_sidecar_under_lease(
        run_dir=run_dir,
        performance_recorder=recorder,
        per_transcript_results=[_per_result()],
        group_errors=[],
        selected_modules=["stats"],
        aggregation_disabled=True,
    )
    assert warning is None
    assert load_run_performance(run_dir).status == RunPerformanceLoadStatus.ok


@pytest.mark.unit
def test_build_group_performance_meta_and_status_matrix() -> None:
    from transcriptx.core.observability.run_performance.schema import (
        ExecutionStatus,
        FinalStatus,
    )

    complete = _per_result(completed=True)
    incomplete = _per_result(completed=False)
    meta = _build_group_performance_meta([complete, incomplete])
    assert meta.member_count == 2
    assert meta.members_completed == 1
    assert meta.members_failed == 1
    assert meta.partial is True

    exec_s, final_s, term = _derive_group_performance_statuses(
        per_transcript_results=[complete],
        group_errors=[],
        aggregation_disabled=True,
        group_phase_terminal_failure=False,
    )
    assert exec_s == ExecutionStatus.succeeded
    assert final_s == FinalStatus.succeeded
    assert term == "aggregation_disabled"

    exec_s, final_s, term = _derive_group_performance_statuses(
        per_transcript_results=[complete, incomplete],
        group_errors=[],
        aggregation_disabled=False,
        group_phase_terminal_failure=False,
    )
    assert exec_s == ExecutionStatus.partial
    assert term == "partial_member_outcomes"

    exec_s, final_s, term = _derive_group_performance_statuses(
        per_transcript_results=[incomplete],
        group_errors=[],
        aggregation_disabled=False,
        group_phase_terminal_failure=False,
    )
    assert exec_s == ExecutionStatus.failed
    assert term == "all_members_failed"

    exec_s, final_s, term = _derive_group_performance_statuses(
        per_transcript_results=[],
        group_errors=[],
        aggregation_disabled=False,
        group_phase_terminal_failure=False,
    )
    assert term == "no_members"

    exec_s, final_s, term = _derive_group_performance_statuses(
        per_transcript_results=[complete],
        group_errors=[],
        aggregation_disabled=False,
        group_phase_terminal_failure=True,
    )
    assert exec_s == ExecutionStatus.failed
    assert term == "group_phase_terminal_failure"


@pytest.mark.unit
def test_sidecar_refuses_run_id_mismatch(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "canonical-id",
                "transcript_key": "gk",
                "modules_enabled": ["stats"],
                "modules_run": ["stats"],
                "modules_skipped": [],
                "modules_failed": [],
                "module_outcomes": [],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    recorder = RunPerformanceRecorder(run_id=PENDING_RUN_ID, target_type="group")
    recorder.set_run_id("different-id")
    recorder.start_wall_clock()
    warning = _write_group_performance_sidecar_under_lease(
        run_dir=run_dir,
        performance_recorder=recorder,
        per_transcript_results=[_per_result()],
        group_errors=[],
        selected_modules=["stats"],
        aggregation_disabled=True,
    )
    assert warning == PERFORMANCE_SIDECAR_RESULTS_UNAVAILABLE
    assert recorder.state == RecorderState.stopped
    assert not (run_dir / ".transcriptx" / "run_performance.json").exists()


@pytest.mark.unit
def test_finalize_disabled_writes_aggregation_disabled_termination(
    tmp_path: Path,
) -> None:
    config = TranscriptXConfig()
    config.group_analysis.enabled = False
    config.group_analysis.output_dir = str(tmp_path / "groups")
    recorder = RunPerformanceRecorder(run_id=PENDING_RUN_ID, target_type="group")
    recorder.start_wall_clock()
    result = finalize_group_analysis(
        scope=_scope(),
        members=[_member()],
        resolved_paths=["/tmp/a.json"],
        per_transcript_results=[_per_result()],
        group_errors=[],
        selected_modules=["stats"],
        config=config,
        performance_recorder=recorder,
    )
    loaded = load_run_performance(Path(result["group_output_dir"]))
    assert loaded.payload is not None
    assert loaded.payload.termination_reason_code == "aggregation_disabled"
    assert loaded.payload.execution_status.value == "succeeded"


@pytest.mark.unit
def test_group_recorder_not_active_during_member_bind() -> None:
    group = RunPerformanceRecorder(run_id=PENDING_RUN_ID, target_type="group")
    group.start_wall_clock()
    assert get_active_recorder() is None

    member = RunPerformanceRecorder(run_id=PENDING_RUN_ID, target_type="transcript")
    member.set_run_id("m1")
    member.start_wall_clock()
    member.bind()
    try:
        assert get_active_recorder() is member
        assert get_active_recorder() is not group
    finally:
        member.unbind()
    assert get_active_recorder() is None
    group.stop_wall_clock()


@pytest.mark.unit
def test_pipeline_group_branch_never_binds_group_recorder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Member execution must not observe the group recorder as active."""
    from transcriptx.core.pipeline import pipeline as pipeline_mod
    from transcriptx.core.pipeline.target_resolver import AnalysisScope

    observed: list[Any] = []

    def fake_single(**_kwargs: Any) -> dict[str, Any]:
        observed.append(get_active_recorder())
        return {
            "transcript_key": "tk",
            "run_id": "mem1",
            "output_dir": str(tmp_path / "mem"),
            "module_results": {},
            "modules_run": ["stats"],
            "skipped_modules": [],
            "errors": [],
        }

    def fake_finalize(**kwargs: Any) -> dict[str, Any]:
        rec = kwargs.get("performance_recorder")
        assert rec is not None
        assert rec.target_type == "group"
        assert get_active_recorder() is None
        # Finalize owns stop/write; stop here so pipeline finally is a no-op.
        if rec.state == RecorderState.running:
            rec.stop_wall_clock()
        return {
            "status": "completed",
            "group_run_id": "g1",
            "group_output_dir": str(tmp_path),
            "errors": [],
        }

    monkeypatch.setattr(
        pipeline_mod,
        "resolve_analysis_target",
        lambda _target: (
            AnalysisScope(
                scope_type="group",
                uuid="g",
                key="gk",
                display_name="G",
            ),
            [
                SimpleNamespace(
                    file_path="/tmp/a.json",
                    file_name="a.json",
                    id=1,
                    uuid="m1",
                )
            ],
        ),
    )
    monkeypatch.setattr(pipeline_mod, "_run_single_analysis_pipeline", fake_single)
    monkeypatch.setattr(pipeline_mod, "finalize_group_analysis", fake_finalize)

    out = pipeline_mod.run_analysis_pipeline(
        target=SimpleNamespace(),  # unused; resolver mocked
        selected_modules=["stats"],
        config=TranscriptXConfig(),
    )
    assert out["status"] == "completed"
    assert observed == [None]
