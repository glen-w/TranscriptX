from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.utils import state_utils


@pytest.mark.unit
def test_validate_processing_state_missing_file(tmp_path: Path):
    state_file = tmp_path / "missing.json"
    out = state_utils.validate_processing_state(state_file=state_file)
    assert out["valid"] is False
    assert out["entries_checked"] == 0


@pytest.mark.unit
def test_validate_processing_state_invalid_json(tmp_path: Path):
    state_file = tmp_path / "processing_state.json"
    state_file.write_text("{bad", encoding="utf-8")
    out = state_utils.validate_processing_state(state_file=state_file)
    assert out["valid"] is False
    assert any("not valid JSON" in e for e in out["errors"])


@pytest.mark.unit
def test_validate_processing_state_collects_path_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    state_file = tmp_path / "processing_state.json"
    state_file.write_text(
        json.dumps(
            {
                "processed_files": {
                    "k": {"transcript_path": "/tmp/x.json", "status": "completed"}
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(state_utils, "validate_state_entry", lambda _e: (True, []))
    monkeypatch.setattr(
        state_utils, "validate_state_paths", lambda _e: (False, ["missing output_dir"])
    )

    out = state_utils.validate_processing_state(state_file=state_file)
    assert out["valid"] is True
    assert out["entries_valid"] == 1
    assert any("missing output_dir" in w for w in out["warnings"])


@pytest.mark.unit
def test_repair_processing_state_dry_run_reports_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    state_file = tmp_path / "processing_state.json"
    state_file.write_text(
        json.dumps(
            {
                "processed_files": {
                    "k": {
                        "transcript_path": str(transcript),
                        "status": "completed",
                        "analysis_status": "partial",
                        "analysis_modules_requested": ["a", "b"],
                        "analysis_modules_run": ["a"],
                        "analysis_modules_failed": [],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(state_utils, "migrate_state_entry", lambda e: e)
    monkeypatch.setattr(
        state_utils, "enrich_state_entry", lambda e, _p: {**e, "enriched": True}
    )
    monkeypatch.setattr(state_utils, "validate_state_entry", lambda _e: (True, []))
    monkeypatch.setattr(
        state_utils, "resolve_file_path", lambda _p, **_k: str(tmp_path / "audio.mp3")
    )

    out = state_utils.repair_processing_state(
        state_file=state_file, backup=False, dry_run=True
    )
    assert out["entries_repaired"] == 1
    assert out["repaired"] is False
    assert out["entries_removed"] == 0


@pytest.mark.unit
def test_repair_processing_state_removes_invalid_and_saves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    state_file = tmp_path / "processing_state.json"
    state_file.write_text(
        json.dumps(
            {
                "processed_files": {
                    "keep": {"transcript_path": str(transcript), "status": "completed"},
                    "drop": {"transcript_path": "missing", "status": "bad"},
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(state_utils, "migrate_state_entry", lambda e: e)
    monkeypatch.setattr(state_utils, "enrich_state_entry", lambda e, _p: e)

    def _validate(e):
        if e.get("status") == "bad":
            return (False, ["bad status"])
        return (True, [])

    monkeypatch.setattr(state_utils, "validate_state_entry", _validate)
    monkeypatch.setattr(
        state_utils,
        "resolve_file_path",
        lambda _p, **_k: (_ for _ in ()).throw(FileNotFoundError()),
    )

    out = state_utils.repair_processing_state(
        state_file=state_file, backup=False, dry_run=False
    )
    assert out["repaired"] is True
    assert out["entries_removed"] == 1
    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert set(saved["processed_files"].keys()) == {"keep"}
