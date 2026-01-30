"""
Tests for processing state recovery and partial-run semantics.
"""

import json
from pathlib import Path

import pytest

from transcriptx.core.utils.state_schema import update_analysis_state
from transcriptx.core.utils.file_lock import FileLock
from transcriptx.cli import processing_state


@pytest.mark.unit
def test_update_analysis_state_partial_run():
    """Partial module runs should mark analysis_status=partial."""
    entry = {
        "processed_at": "2024-01-01T00:00:00",
        "status": "completed",
    }
    results = {
        "selected_modules": ["sentiment", "stats"],
        "modules_run": ["sentiment"],
        "errors": ["Error in stats module"],
        "duration": 12.5,
        "execution_order": ["sentiment", "stats"],
    }

    updated = update_analysis_state(entry, results)

    assert updated["analysis_status"] == "partial"
    assert "stats" in updated["analysis_modules_failed"]
    assert updated["analysis_modules_run"] == ["sentiment"]


@pytest.mark.unit
def test_load_processing_state_when_locked(tmp_path, monkeypatch):
    """Locked state file should return empty state to avoid corruption."""
    state_file = tmp_path / "processing_state.json"
    state_file.write_text(json.dumps({"processed_files": {"file": {"status": "completed"}}}))
    monkeypatch.setattr(processing_state, "PROCESSING_STATE_FILE", state_file)

    with FileLock(state_file, blocking=True) as lock:
        assert lock.acquired is True
        loaded = processing_state.load_processing_state(validate=False)

    assert loaded == {"processed_files": {}}
