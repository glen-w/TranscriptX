import json

import pytest

from transcriptx.core.utils import state_utils


@pytest.mark.unit
def test_list_transcripts_with_analysis_filters_not_started(tmp_path, monkeypatch):
    state_file = tmp_path / "processing_state.json"
    state_file.write_text(
        json.dumps(
            {
                "processed_files": {
                    "a.wav": {
                        "transcript_path": "/tmp/a.json",
                        "analysis_status": "completed",
                        "analysis_modules_requested": ["stats", "sentiment"],
                        "analysis_modules_run": ["stats", "sentiment"],
                        "analysis_completed": True,
                    },
                    "b.wav": {
                        "transcript_path": "/tmp/b.json",
                        "analysis_status": "not_started",
                    },
                }
            }
        )
    )
    monkeypatch.setattr(state_utils, "PROCESSING_STATE_FILE", state_file)

    results = state_utils.list_transcripts_with_analysis()

    assert len(results) == 1
    assert results[0]["transcript_path"] == "/tmp/a.json"
    assert results[0]["analysis_status"]["status"] == "completed"


@pytest.mark.unit
def test_list_transcripts_needing_analysis_without_module_filter(tmp_path, monkeypatch):
    state_file = tmp_path / "processing_state.json"
    state_file.write_text(
        json.dumps(
            {
                "processed_files": {
                    "a.wav": {
                        "transcript_path": "/tmp/a.json",
                        "analysis_status": "completed",
                        "analysis_modules_requested": ["stats"],
                        "analysis_modules_run": ["stats"],
                    },
                    "b.wav": {
                        "transcript_path": "/tmp/b.json",
                        "analysis_status": "partial",
                        "analysis_modules_requested": ["stats", "sentiment"],
                        "analysis_modules_run": ["stats"],
                    },
                    "c.wav": {
                        "transcript_path": "/tmp/c.json",
                        "analysis_status": "failed",
                    },
                    "d.wav": {
                        "transcript_path": "/tmp/d.json",
                        "analysis_status": "not_started",
                    },
                }
            }
        )
    )
    monkeypatch.setattr(state_utils, "PROCESSING_STATE_FILE", state_file)

    needing = state_utils.list_transcripts_needing_analysis()

    assert set(needing) == {"/tmp/b.json", "/tmp/c.json", "/tmp/d.json"}


@pytest.mark.unit
def test_list_transcripts_needing_analysis_with_module_filter(tmp_path, monkeypatch):
    state_file = tmp_path / "processing_state.json"
    state_file.write_text(
        json.dumps(
            {
                "processed_files": {
                    "a.wav": {
                        "transcript_path": "/tmp/a.json",
                        "analysis_status": "completed",
                        "analysis_modules_requested": ["stats", "sentiment"],
                        "analysis_modules_run": ["stats", "sentiment"],
                        "analysis_completed": True,
                    },
                    "b.wav": {
                        "transcript_path": "/tmp/b.json",
                        "analysis_status": "completed",
                        "analysis_modules_requested": ["stats"],
                        "analysis_modules_run": ["stats"],
                        "analysis_completed": True,
                    },
                    "c.wav": {
                        "transcript_path": "/tmp/c.json",
                        "analysis_status": "partial",
                        "analysis_modules_requested": ["stats", "sentiment"],
                        "analysis_modules_run": ["stats"],
                    },
                }
            }
        )
    )
    monkeypatch.setattr(state_utils, "PROCESSING_STATE_FILE", state_file)

    needing = state_utils.list_transcripts_needing_analysis(
        modules=["stats", "sentiment"]
    )

    assert set(needing) == {"/tmp/b.json", "/tmp/c.json"}


@pytest.mark.unit
def test_has_analysis_completed_fallback_uses_requested_coverage(monkeypatch):
    history = {
        "status": "completed",
        "completed": True,
        "modules_requested": ["stats", "sentiment"],
        "modules_run": [],
    }
    monkeypatch.setattr(state_utils, "get_analysis_history", lambda _path: history)

    assert state_utils.has_analysis_completed("/tmp/a.json", ["stats"]) is True
    assert state_utils.has_analysis_completed("/tmp/a.json", ["emotion"]) is False


@pytest.mark.unit
def test_get_missing_modules_returns_requested_when_no_history(monkeypatch):
    monkeypatch.setattr(state_utils, "get_analysis_history", lambda _path: None)

    missing = state_utils.get_missing_modules("/tmp/none.json", ["stats", "sentiment"])

    assert missing == ["stats", "sentiment"]


@pytest.mark.unit
def test_get_analysis_history_returns_none_when_not_found(monkeypatch):
    monkeypatch.setattr(
        state_utils, "load_processing_state", lambda: {"processed_files": {}}
    )

    assert state_utils.get_analysis_history("/tmp/unknown.json") is None
