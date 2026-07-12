"""Unit tests for file-backed pipeline port adapters."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from transcriptx.core.pipeline.adapters.artifact_manifest_store import (
    ArtifactManifestStore,
)
from transcriptx.core.pipeline.adapters.event_callback_sink import EventCallbackSink
from transcriptx.core.pipeline.adapters.file_config_snapshot_store import (
    FileConfigSnapshotStore,
)
from transcriptx.core.pipeline.adapters.file_execution_plan_store import (
    FileExecutionPlanStore,
)
from transcriptx.core.pipeline.adapters.file_run_report_store import FileRunReportStore
from transcriptx.core.pipeline.adapters.file_run_state_store import FileRunStateStore
from transcriptx.core.pipeline.adapters.logging_reporter import LoggingReporter
from transcriptx.core.pipeline.contracts import ExecutionPlan


def _minimal_plan() -> ExecutionPlan:
    return ExecutionPlan(
        requested=["stats"],
        runnable=["stats"],
        dependency_added=[],
        blocked={},
        skipped_preflight=[],
        deterministic_order=["stats"],
        plan_hash="abc",
    )


@pytest.mark.unit
def test_file_execution_plan_store_save_writes_json(tmp_path: Path) -> None:
    store = FileExecutionPlanStore()
    out = store.save(_minimal_plan(), str(tmp_path))
    assert out.success is True
    path = tmp_path / ".transcriptx" / "execution_plan.json"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "stats" in text
    assert "plan_hash" in text


@pytest.mark.unit
def test_file_execution_plan_store_save_returns_failure_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileExecutionPlanStore()

    def _boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(
        "transcriptx.core.pipeline.adapters.file_execution_plan_store.write_json",
        _boom,
    )
    out = store.save(_minimal_plan(), str(tmp_path))
    assert out.success is False
    assert out.error_message == "disk full"


@pytest.mark.unit
def test_file_run_report_store_success_and_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileRunReportStore()
    fake_report = object()
    monkeypatch.setattr(
        "transcriptx.core.pipeline.adapters.file_run_report_store.save_run_report",
        lambda rep, od: None,
    )
    out = store.save(str(tmp_path), fake_report)
    assert out.success is True

    def _fail(_rep, _od):
        raise RuntimeError("persist")

    monkeypatch.setattr(
        "transcriptx.core.pipeline.adapters.file_run_report_store.save_run_report",
        _fail,
    )
    out2 = store.save(str(tmp_path), fake_report)
    assert out2.success is False
    assert "persist" in (out2.error_message or "")


@pytest.mark.unit
def test_file_config_snapshot_store_success_and_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileConfigSnapshotStore()
    out = store.save(str(tmp_path), {"k": 1})
    assert out.success is True
    snap = tmp_path / ".transcriptx" / "run_config_snapshot.json"
    assert snap.exists()

    monkeypatch.setattr(
        "transcriptx.core.pipeline.adapters.file_config_snapshot_store.write_json",
        lambda *_a, **_k: (_ for _ in ()).throw(ValueError("bad")),
    )
    out2 = store.save(str(tmp_path), {})
    assert out2.success is False


@pytest.mark.unit
def test_file_run_state_store_skips_when_no_state_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileRunStateStore()
    fake_state = tmp_path / "missing_state.json"
    monkeypatch.setattr(
        "transcriptx.core.pipeline.adapters.file_run_state_store.PROCESSING_STATE_FILE",
        fake_state,
    )
    out = store.update({"transcript_path": str(tmp_path / "t.json")})
    assert out.success is True
    assert out.name == "processing_state"


@pytest.mark.unit
def test_file_run_state_store_skips_when_transcript_path_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileRunStateStore()
    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.core.pipeline.adapters.file_run_state_store.PROCESSING_STATE_FILE",
        state_file,
    )
    out = store.update({})
    assert out.success is True
    assert out.severity == "optional"


@pytest.mark.unit
def test_file_run_state_store_skips_when_entry_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileRunStateStore()
    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.core.pipeline.adapters.file_run_state_store.PROCESSING_STATE_FILE",
        state_file,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.adapters.file_run_state_store.load_processing_state",
        lambda: {"processed_files": {}},
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.adapters.file_run_state_store.find_processed_entry_for_path",
        lambda *_a, **_k: (None, None),
    )
    out = store.update({"transcript_path": str(tmp_path / "t.json")})
    assert out.success is True
    assert out.severity == "optional"


@pytest.mark.unit
def test_file_run_state_store_updates_matching_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileRunStateStore()
    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.core.pipeline.adapters.file_run_state_store.PROCESSING_STATE_FILE",
        state_file,
    )
    state = {"processed_files": {"k1": {"path": "t.json"}}}
    saved: list = []
    monkeypatch.setattr(
        "transcriptx.core.pipeline.adapters.file_run_state_store.load_processing_state",
        lambda: state,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.adapters.file_run_state_store.find_processed_entry_for_path",
        lambda *_a, **_k: ("k1", state["processed_files"]["k1"]),
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.adapters.file_run_state_store.update_analysis_state",
        lambda entry, results: {**entry, "modules_run": results.get("modules_run")},
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.adapters.file_run_state_store.save_processing_state",
        lambda s: saved.append(s),
    )
    out = store.update(
        {"transcript_path": str(tmp_path / "t.json"), "modules_run": ["stats"]}
    )
    assert out.success is True
    assert out.severity == "required"
    assert saved[0]["processed_files"]["k1"]["modules_run"] == ["stats"]


@pytest.mark.unit
def test_file_run_state_store_failure_returns_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileRunStateStore()
    monkeypatch.setattr(
        "transcriptx.core.pipeline.adapters.file_run_state_store.PROCESSING_STATE_FILE",
        tmp_path / "state.json",
    )
    (tmp_path / "state.json").write_text("{}", encoding="utf-8")

    def _boom():
        raise RuntimeError("load failed")

    monkeypatch.setattr(
        "transcriptx.core.pipeline.adapters.file_run_state_store.load_processing_state",
        _boom,
    )
    out = store.update({"transcript_path": str(tmp_path / "t.json")})
    assert out.success is False
    assert "load failed" in (out.error_message or "")


@pytest.mark.unit
def test_artifact_manifest_store_save_and_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ArtifactManifestStore()
    monkeypatch.setattr(
        "transcriptx.core.pipeline.adapters.artifact_manifest_store.save_run_manifest",
        lambda *_a, **_k: None,
    )
    out = store.save_manifest({"run_id": "r1"}, str(tmp_path))
    assert out.success is True

    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    rows = store.index_artifacts(str(tmp_path))
    paths = {r["path"] for r in rows}
    assert "a.txt" in paths
    assert not any(r["path"] == "manifest.json" for r in rows)
    assert all("checksum" in r for r in rows)


@pytest.mark.unit
def test_artifact_manifest_store_save_manifest_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ArtifactManifestStore()

    def _fail(*_a, **_k):
        raise OSError("no space")

    monkeypatch.setattr(
        "transcriptx.core.pipeline.adapters.artifact_manifest_store.save_run_manifest",
        _fail,
    )
    out = store.save_manifest({}, str(tmp_path))
    assert out.success is False


@pytest.mark.unit
def test_event_callback_sink_collects_and_swallows_callback_errors() -> None:
    events: list[dict] = []
    boom = MagicMock(side_effect=RuntimeError("cb"))

    sink = EventCallbackSink(on_event=boom, event_collector=events)
    sink.emit({"event": "x"})
    assert events == [{"event": "x"}]
    boom.assert_called_once()


@pytest.mark.unit
def test_event_callback_sink_no_callback_no_collector() -> None:
    sink = EventCallbackSink()
    sink.emit({"ok": True})


@pytest.mark.unit
def test_logging_reporter_methods() -> None:
    rep = LoggingReporter()
    rep.info("i")
    rep.warning("w")
    rep.error("e")
