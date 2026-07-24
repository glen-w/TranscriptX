"""Tests for retained-run performance snapshot exporter (Phase 2)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from transcriptx.core.observability.run_performance.exporter import (
    BANNED_LABEL_KEYS,
    SnapshotExportConfig,
    assert_no_banned_labels,
    build_retained_run_snapshot,
    export_retained_run_snapshot,
    render_prometheus_textfile,
)
from transcriptx.core.observability.run_performance.inventory import (
    scan_committed_runs,
)
from transcriptx.core.observability.run_performance.io import write_run_performance
from transcriptx.core.observability.run_performance.schema import (
    CacheProvenance,
    ExecutionStatus,
    FinalStatus,
    LlmAggregate,
    RunPerformanceV1,
)
from transcriptx.core.pipeline.manifest_builder import (
    build_run_results_summary,
    write_run_results_summary,
)


def _write_committed_transcript_run(
    outputs: Path,
    *,
    slug: str,
    run_id: str,
    wall_ms: float,
    mode: str = "quick",
    modules: list[tuple[str, str, float | None]] | None = None,
    with_sidecar: bool = True,
    llm: LlmAggregate | None = None,
) -> Path:
    run_root = outputs / slug / run_id
    run_root.mkdir(parents=True)
    module_rows = modules or [("stats", "run", 10.0)]
    enabled = [m[0] for m in module_rows]
    ran = [m[0] for m in module_rows if m[1] in {"run", "succeeded", "failed"}]
    terminal = {
        mid: {"duration_ms": dur}
        for mid, status, dur in module_rows
        if dur is not None and status in {"run", "succeeded", "failed"}
    }
    write_run_results_summary(
        run_dir=run_root,
        run_id=run_id,
        transcript_key=f"tk-{run_id}",
        modules_enabled=enabled,
        modules_run=ran,
        skipped_modules=[],
        errors=[],
        terminal_outcomes=terminal,
    )
    if with_sidecar:
        snap = RunPerformanceV1(
            run_id=run_id,
            target_type="transcript",
            wall_clock_duration_ms=wall_ms,
            execution_status=ExecutionStatus.succeeded,
            final_status=FinalStatus.succeeded,
            cache_provenance=CacheProvenance.none_recorded,
            analysis={"mode": mode, "profile": "default"},
            llm=llm,
        )
        write_run_performance(run_root, snap)
    return run_root


def _write_committed_group_run(
    groups: Path,
    *,
    group_id: str,
    run_id: str,
    wall_ms: float,
) -> Path:
    run_root = groups / group_id / run_id
    run_root.mkdir(parents=True)
    write_run_results_summary(
        run_dir=run_root,
        run_id=run_id,
        transcript_key=f"group:{group_id}",
        modules_enabled=["stats"],
        modules_run=["stats"],
        skipped_modules=[],
        errors=[],
        terminal_outcomes={"stats": {"duration_ms": 5.0}},
    )
    snap = RunPerformanceV1(
        run_id=run_id,
        target_type="group",
        wall_clock_duration_ms=wall_ms,
        execution_status=ExecutionStatus.succeeded,
        final_status=FinalStatus.succeeded,
        cache_provenance=CacheProvenance.none_recorded,
        analysis={"mode": "full"},
        group={"member_count": 2, "partial": False},
    )
    write_run_performance(run_root, snap)
    return run_root


@pytest.mark.unit
def test_scan_committed_runs_finds_transcript_and_group(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    groups = outputs / "groups"
    _write_committed_transcript_run(outputs, slug="a", run_id="r1", wall_ms=1000.0)
    _write_committed_group_run(groups, group_id="g1", run_id="gr1", wall_ms=2000.0)
    (outputs / "a" / "incomplete").mkdir(parents=True)
    bad = outputs / "a" / "bad"
    bad.mkdir()
    (bad / "run_results.json").write_text("{not-json", encoding="utf-8")

    result = scan_committed_runs(outputs_dir=outputs, group_outputs_dir=groups)
    assert len(result.runs) == 2
    types = sorted(r.target_type for r in result.runs)
    assert types == ["group", "transcript"]
    assert result.candidates_seen >= 3


@pytest.mark.unit
def test_scan_respects_max_runs(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    for i in range(5):
        _write_committed_transcript_run(
            outputs, slug="s", run_id=f"r{i}", wall_ms=100.0 * i
        )
    result = scan_committed_runs(outputs_dir=outputs, max_runs=2)
    assert len(result.runs) == 2
    assert result.truncated is True


@pytest.mark.unit
def test_export_deletion_shrinks_gauges(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    textfile = tmp_path / "snapshot.prom"
    r1 = _write_committed_transcript_run(
        outputs, slug="s", run_id="keep", wall_ms=1500.0
    )
    r2 = _write_committed_transcript_run(
        outputs, slug="s", run_id="drop", wall_ms=2500.0
    )
    config = SnapshotExportConfig(
        outputs_dir=outputs,
        group_outputs_dir=outputs / "groups",
        textfile_path=textfile,
        duration_buckets_s=(1.0, 5.0),
    )
    first = export_retained_run_snapshot(config)
    assert first.runs_exported == 2
    body1 = textfile.read_text(encoding="utf-8")
    assert "transcriptx_retained_runs{" in body1
    assert 'target_type="transcript"' in body1
    assert (
        'transcriptx_retained_run_wall_seconds_bucket{le="5",target_type="transcript"} 2'
        in body1
    )

    shutil.rmtree(r2)
    assert r1.exists()

    second = export_retained_run_snapshot(config)
    assert second.runs_exported == 1
    body2 = textfile.read_text(encoding="utf-8")
    assert (
        'transcriptx_retained_run_wall_seconds_bucket{le="+Inf",target_type="transcript"} 1'
        in body2
    )
    assert "TYPE transcriptx_retained_runs gauge" in body2
    assert "# TYPE " in body2
    assert "\n# TYPE " in ("\n" + body2)
    assert all(
        line.startswith("# TYPE ") and line.endswith(" gauge")
        for line in body2.splitlines()
        if line.startswith("# TYPE ")
    )
    state_siblings = [p for p in textfile.parent.iterdir() if p.name != textfile.name]
    assert not any("mtime" in p.name or "ingest" in p.name for p in state_siblings)


@pytest.mark.unit
def test_textfile_bans_high_cardinality_labels(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    _write_committed_transcript_run(
        outputs,
        slug="s",
        run_id="secret-run-id",
        wall_ms=500.0,
        llm=LlmAggregate(
            call_count=2,
            success_count=2,
            failure_count=0,
            retry_count=0,
            logical_wall_ms=10.0,
            models=["llama3.2:latest"],
        ),
    )
    inventory = scan_committed_runs(outputs_dir=outputs)
    snapshot = build_retained_run_snapshot(inventory, duration_buckets_s=(1.0, 5.0))
    assert_no_banned_labels(snapshot.samples)
    body = render_prometheus_textfile(snapshot)
    for banned in BANNED_LABEL_KEYS:
        assert f"{banned}=" not in body
    assert "secret-run-id" not in body
    assert "tk-secret-run-id" not in body
    assert str(outputs) not in body
    assert 'model="llama3.2:latest"' in body
    assert 'result="success"' in body


@pytest.mark.unit
def test_runs_without_sidecar_still_count_modules(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    _write_committed_transcript_run(
        outputs,
        slug="s",
        run_id="noside",
        wall_ms=0.0,
        with_sidecar=False,
        modules=[("emotion", "run", 42.0)],
    )
    inventory = scan_committed_runs(outputs_dir=outputs)
    snapshot = build_retained_run_snapshot(inventory, duration_buckets_s=(1.0,))
    assert snapshot.runs_without_sidecar == 1
    assert snapshot.runs_with_sidecar == 0
    body = render_prometheus_textfile(snapshot)
    assert 'module_id="emotion"' in body
    assert 'execution_status="unknown"' in body
    assert "transcriptx_retained_run_wall_seconds_count{" not in body


@pytest.mark.unit
def test_histogram_buckets_are_cumulative(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    _write_committed_transcript_run(outputs, slug="s", run_id="fast", wall_ms=500.0)
    _write_committed_transcript_run(outputs, slug="s", run_id="mid", wall_ms=3000.0)
    inventory = scan_committed_runs(outputs_dir=outputs)
    snapshot = build_retained_run_snapshot(inventory, duration_buckets_s=(1.0, 5.0))
    body = render_prometheus_textfile(snapshot)
    assert (
        'transcriptx_retained_run_wall_seconds_bucket{le="1",target_type="transcript"} 1'
        in body
    )
    assert (
        'transcriptx_retained_run_wall_seconds_bucket{le="5",target_type="transcript"} 2'
        in body
    )
    assert (
        'transcriptx_retained_run_wall_seconds_bucket{le="+Inf",target_type="transcript"} 2'
        in body
    )


@pytest.mark.unit
def test_invalid_run_results_payload_not_exported(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    run_root = outputs / "s" / "x"
    run_root.mkdir(parents=True)
    (run_root / "run_results.json").write_text(
        json.dumps({"schema_version": 1, "run_id": ""}), encoding="utf-8"
    )
    result = scan_committed_runs(outputs_dir=outputs)
    assert result.runs == ()


@pytest.mark.unit
def test_config_from_env_overrides_keep_groups_under_outputs(tmp_path: Path) -> None:
    from transcriptx.core.observability.run_performance.exporter import config_from_env

    out = tmp_path / "custom_outputs"
    cfg = config_from_env(outputs_dir=out, textfile_path=tmp_path / "x.prom")
    assert cfg.outputs_dir == out
    assert cfg.group_outputs_dir == out / "groups"


@pytest.mark.unit
def test_build_run_results_helper_still_round_trips() -> None:
    payload = build_run_results_summary(
        run_id="r",
        transcript_key="tk",
        modules_enabled=["stats"],
        modules_run=["stats"],
        skipped_modules=[],
        errors=[],
        terminal_outcomes={"stats": {"duration_ms": 1.0}},
    )
    assert payload["run_id"] == "r"
