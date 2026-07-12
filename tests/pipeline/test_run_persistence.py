"""Unit tests for PersistenceLayer run/state/report/manifest outcomes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from transcriptx.core.pipeline.contracts import ErrorKind, RunConfigSnapshot
from transcriptx.core.pipeline.run_persistence import PersistenceLayer


@pytest.fixture
def layer() -> PersistenceLayer:
    return PersistenceLayer()


@pytest.mark.unit
def test_persist_run_outputs_success_and_failure(
    layer: PersistenceLayer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.persist_canonical_results_and_artifacts",
        lambda **_k: {"run_results_path": tmp_path / "run_results.json"},
    )
    ok = layer.persist_run_outputs(
        output_dir=str(tmp_path),
        run_id="r1",
        transcript_key="tk",
        selected_modules=["stats"],
        results={"modules_run": ["stats"], "skipped_modules": [], "errors": []},
    )
    assert ok.success is True
    assert ok.name == "canonical_results"

    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.persist_canonical_results_and_artifacts",
        lambda **_k: (_ for _ in ()).throw(RuntimeError("disk")),
    )
    bad = layer.persist_run_outputs(
        output_dir=str(tmp_path),
        run_id="r1",
        transcript_key="tk",
        selected_modules=["stats"],
        results={},
    )
    assert bad.success is False
    assert bad.error_kind == ErrorKind.PERSISTENCE
    assert "disk" in (bad.error_message or "")


@pytest.mark.unit
def test_persist_processing_state_optional_when_missing_file(
    layer: PersistenceLayer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "no_state.json"
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.PROCESSING_STATE_FILE",
        missing,
    )
    out = layer.persist_processing_state(str(tmp_path / "t.json"), {"modules_run": []})
    assert out.success is True
    assert out.severity == "optional"


@pytest.mark.unit
def test_persist_processing_state_optional_when_entry_missing(
    layer: PersistenceLayer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.PROCESSING_STATE_FILE",
        state_file,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.load_processing_state",
        lambda: {"processed_files": {}},
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.find_processed_entry_for_path",
        lambda *_a, **_k: (None, None),
    )
    out = layer.persist_processing_state(str(tmp_path / "t.json"), {})
    assert out.success is True
    assert out.severity == "optional"


@pytest.mark.unit
def test_persist_processing_state_updates_and_saves(
    layer: PersistenceLayer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.PROCESSING_STATE_FILE",
        state_file,
    )
    state = {"processed_files": {"k1": {"path": "t.json"}}}
    saved: list = []

    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.load_processing_state",
        lambda: state,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.find_processed_entry_for_path",
        lambda *_a, **_k: ("k1", state["processed_files"]["k1"]),
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.update_analysis_state",
        lambda entry, results: {**entry, "updated": True},
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.save_processing_state",
        lambda s: saved.append(s),
    )
    out = layer.persist_processing_state(
        str(tmp_path / "t.json"), {"modules_run": ["stats"]}
    )
    assert out.success is True
    assert out.severity == "required"
    assert saved[0]["processed_files"]["k1"]["updated"] is True


@pytest.mark.unit
def test_persist_processing_state_failure(
    layer: PersistenceLayer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.PROCESSING_STATE_FILE",
        tmp_path / "state.json",
    )
    (tmp_path / "state.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.load_processing_state",
        lambda: (_ for _ in ()).throw(RuntimeError("locked")),
    )
    out = layer.persist_processing_state(str(tmp_path / "t.json"), {})
    assert out.success is False
    assert "locked" in (out.error_message or "")


@pytest.mark.unit
def test_persist_run_report_success_and_failure(
    layer: PersistenceLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.save_run_report",
        lambda *_a, **_k: None,
    )
    assert layer.persist_run_report(MagicMock(), "/tmp/out").success is True

    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.save_run_report",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("io")),
    )
    bad = layer.persist_run_report(MagicMock(), "/tmp/out")
    assert bad.success is False
    assert bad.error_kind == ErrorKind.PERSISTENCE


@pytest.mark.unit
def test_persist_manifest_indexes_artifacts_and_handles_failure(
    layer: PersistenceLayer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "a.txt").write_text("hi", encoding="utf-8")
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.compute_file_hash",
        lambda _p: "deadbeef",
    )
    captured: dict = {}

    def _create(**kwargs):
        captured.update(kwargs)
        return {"run_id": kwargs["run_id"]}

    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.create_run_manifest",
        _create,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.save_run_manifest",
        lambda *_a, **_k: None,
    )
    snapshot = RunConfigSnapshot(
        config_hash="ch",
        config_source="default",
        draft_override_applied=True,
        schema_version=1,
    )
    out = layer.persist_manifest(
        output_dir=str(tmp_path),
        selected_modules=["stats"],
        transcript_path="/t.json",
        source_basename="t",
        run_id="r1",
        transcript_key="tk",
        transcript_identity_hash="id",
        transcript_content_hash_full="content",
        transcript_file_hash="filehash",
        canonical_schema_version=1,
        config_snapshot=snapshot,
        draft_override_used=True,
    )
    assert out.success is True
    paths = {row["path"] for row in captured["artifact_index"]}
    assert "data/a.txt" in paths
    assert "manifest.json" not in paths
    assert captured["config_override_path"] == ".transcriptx/run_config_override.json"

    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_persistence.create_run_manifest",
        lambda **_k: (_ for _ in ()).throw(ValueError("bad manifest")),
    )
    bad = layer.persist_manifest(
        output_dir=str(tmp_path),
        selected_modules=[],
        transcript_path="/t.json",
        source_basename="t",
        run_id="r2",
        transcript_key="tk",
        transcript_identity_hash="id",
        transcript_content_hash_full="content",
        transcript_file_hash=None,
        canonical_schema_version=1,
        config_snapshot=snapshot,
        draft_override_used=False,
    )
    assert bad.success is False
    assert "bad manifest" in (bad.error_message or "")
