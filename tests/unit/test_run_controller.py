"""Unit tests for run controller manifest loading semantics."""

from __future__ import annotations

import json
from pathlib import Path

import transcriptx.app.controllers.run_controller as rc
from transcriptx.app.controllers.run_controller import _load_manifest


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_manifest_prefers_artifact_manifest(tmp_path: Path) -> None:
    run_dir = tmp_path / "runA"
    _write_json(
        run_dir / "manifest.json",
        {"manifest_type": "artifact_manifest", "run_id": "r1", "artifacts": []},
    )
    _write_json(
        run_dir / ".transcriptx" / "manifest.json",
        {"manifest_type": "run_manifest", "run_id": "r1"},
    )

    manifest = _load_manifest(run_dir)
    assert manifest is not None
    assert manifest.get("manifest_type") == "artifact_manifest"


def test_load_manifest_falls_back_to_run_manifest(tmp_path: Path) -> None:
    run_dir = tmp_path / "runB"
    _write_json(
        run_dir / ".transcriptx" / "manifest.json",
        {"manifest_type": "run_manifest", "run_id": "r2"},
    )

    manifest = _load_manifest(run_dir)
    assert manifest is not None
    assert manifest.get("manifest_type") == "run_manifest"


def test_load_manifest_returns_none_when_invalid(tmp_path: Path) -> None:
    run_dir = tmp_path / "runC"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text("{bad json", encoding="utf-8")

    manifest = _load_manifest(run_dir)
    assert manifest is None


def test_list_recent_runs_prefers_run_results_status_over_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    base = tmp_path / "outputs"
    run_dir = base / "slug" / "run1"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        run_dir / "manifest.json",
        {
            "manifest_type": "artifact_manifest",
            "run_id": "run1",
            "run_metadata": {"status": "completed", "modules_run": ["stats"]},
            "artifacts": [],
        },
    )
    _write_json(
        run_dir / "run_results.json",
        {
            "schema_version": 2,
            "run_id": "run1",
            "transcript_key": "tk",
            "modules_enabled": ["stats"],
            "modules_run": [],
            "modules_skipped": [],
            "modules_failed": ["stats"],
            "errors": ["stats failed"],
            "module_outcomes": [],
        },
    )
    monkeypatch.setattr(rc, "OUTPUTS_DIR", str(base))
    runs = rc.RunController().list_recent_runs(limit=5)
    assert len(runs) == 1
    assert runs[0].status == "failed"


def test_list_recent_runs_falls_back_to_manifest_when_run_results_missing(
    tmp_path: Path, monkeypatch
) -> None:
    base = tmp_path / "outputs"
    run_dir = base / "slug" / "run2"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        run_dir / "manifest.json",
        {
            "manifest_type": "artifact_manifest",
            "run_id": "run2",
            "run_metadata": {"status": "completed", "modules_run": ["stats"]},
            "artifacts": [],
        },
    )
    monkeypatch.setattr(rc, "OUTPUTS_DIR", str(base))
    runs = rc.RunController().list_recent_runs(limit=5)
    assert len(runs) == 1
    assert runs[0].status == "completed"
