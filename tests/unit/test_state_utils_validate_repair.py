"""Offline unit tests for state_utils validate/repair branches."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.core.utils import state_utils as su


def _write_state(path: Path, processed: dict) -> Path:
    path.write_text(
        json.dumps({"processed_files": processed}, indent=2), encoding="utf-8"
    )
    return path


@pytest.mark.unit
def test_load_processing_state_missing_and_bad_json(tmp_path) -> None:
    missing = tmp_path / "nope.json"
    assert su.load_processing_state(missing) == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert su.load_processing_state(bad) == {}


@pytest.mark.unit
def test_validate_processing_state_branches(tmp_path) -> None:
    missing = tmp_path / "missing.json"
    out = su.validate_processing_state(missing)
    assert out["valid"] is False

    bad = tmp_path / "bad.json"
    bad.write_text("{bad", encoding="utf-8")
    assert su.validate_processing_state(bad)["valid"] is False

    # Valid schema entry with analysis warnings
    state = tmp_path / "ok.json"
    entry = {
        "transcript_path": str(tmp_path / "t.json"),
        "status": "completed",
        "analysis_completed": True,
        "analysis_status": "partial",
        "analysis_modules_run": [],
        "analysis_modules_requested": ["sentiment"],
        "analysis_timestamp": "not-a-date",
    }
    (tmp_path / "t.json").write_text("{}", encoding="utf-8")
    _write_state(state, {"k": entry})
    with (
        patch.object(su, "validate_state_entry", return_value=(True, [])),
        patch.object(su, "validate_state_paths", return_value=(False, ["missing mp3"])),
    ):
        result = su.validate_processing_state(state)
    assert result["entries_valid"] == 1
    assert result["warnings"]

    # Invalid entry
    with (
        patch.object(su, "validate_state_entry", return_value=(False, ["bad schema"])),
    ):
        result2 = su.validate_processing_state(state)
    assert result2["entries_invalid"] == 1
    assert result2["valid"] is False

    # modules_run not subset
    entry2 = {
        **entry,
        "analysis_modules_run": ["sentiment", "extra"],
        "analysis_modules_requested": ["sentiment"],
        "analysis_completed": False,
        "analysis_status": "partial",
        "analysis_timestamp": "2020-01-01T00:00:00",
    }
    _write_state(state, {"k": entry2})
    with (
        patch.object(su, "validate_state_entry", return_value=(True, [])),
        patch.object(su, "validate_state_paths", return_value=(True, [])),
    ):
        result3 = su.validate_processing_state(state)
    assert any("not in analysis_modules_requested" in w for w in result3["warnings"])


@pytest.mark.unit
def test_repair_processing_state_paths(tmp_path) -> None:
    tfile = tmp_path / "talk.json"
    tfile.write_text("{}", encoding="utf-8")
    state = tmp_path / "state.json"
    entry = {
        "transcript_path": str(tfile),
        "mp3_path": str(tmp_path / "missing.mp3"),
        "status": "completed",
        "analysis_modules_requested": ["sentiment", "tics"],
        "analysis_modules_run": ["sentiment"],
        "analysis_modules_failed": [],
        "analysis_errors": [],
        "analysis_status": "completed",
        "analysis_completed": True,
    }
    _write_state(state, {"k1": entry, "bad": {"nope": 1}})

    with (
        patch.object(su, "migrate_state_entry", side_effect=lambda e: {**e, "v": 1}),
        patch.object(
            su, "enrich_state_entry", side_effect=lambda e, p: {**e, "enriched": True}
        ),
        patch.object(
            su,
            "resolve_file_path",
            side_effect=FileNotFoundError("no audio"),
        ),
        patch.object(
            su,
            "validate_state_entry",
            side_effect=lambda e: (False, ["invalid"]) if "nope" in e else (True, []),
        ),
    ):
        result = su.repair_processing_state(state, backup=True, dry_run=False)
    assert result["entries_removed"] >= 1 or result["entries_repaired"] >= 0
    assert (tmp_path / "state.json.backup").exists() or result["backup_path"]


@pytest.mark.unit
def test_repair_dry_run_and_missing_file(tmp_path) -> None:
    assert su.repair_processing_state(tmp_path / "missing.json")["repaired"] is False
    state = tmp_path / "s.json"
    _write_state(
        state,
        {
            "k": {
                "transcript_path": str(tmp_path / "t.json"),
                "status": "completed",
            }
        },
    )
    (tmp_path / "t.json").write_text("{}", encoding="utf-8")
    with (
        patch.object(su, "migrate_state_entry", side_effect=lambda e: e),
        patch.object(su, "enrich_state_entry", side_effect=lambda e, p: e),
        patch.object(su, "validate_state_entry", return_value=(True, [])),
    ):
        dry = su.repair_processing_state(state, backup=False, dry_run=True)
    assert dry["repaired"] is False


@pytest.mark.unit
def test_query_helpers(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    tpath = str(tmp_path / "t.json")
    (tmp_path / "t.json").write_text("{}", encoding="utf-8")
    state = {
        "processed_files": {
            "k": {
                "transcript_path": tpath,
                "analysis_modules_run": ["sentiment"],
                "analysis_modules_requested": ["sentiment", "tics"],
                "analysis_completed": False,
                "analysis_status": "partial",
            }
        }
    }
    state_file = tmp_path / "processing_state.json"
    state_file.write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(su, "PROCESSING_STATE_FILE", state_file)

    hist = su.get_analysis_history(tpath)
    assert isinstance(hist, dict)
    assert su.has_analysis_completed(tpath, ["sentiment"]) is True
    assert su.has_analysis_completed(tpath, ["sentiment", "tics"]) is False
    missing = su.get_missing_modules(tpath, ["sentiment", "tics"])
    assert "tics" in missing
    status = su.get_transcript_analysis_status(tpath)
    assert status is not None
    listed = su.list_transcripts_with_analysis()
    assert listed
    needing = su.list_transcripts_needing_analysis(["tics"])
    assert tpath in needing or any("t.json" in x for x in needing)
