"""
Unit tests for state_schema.py: schema validation, migration, enrichment,
analysis-state tracking.

These tests are fast, deterministic, and require no external services.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from transcriptx.core.utils.state_schema import (
    STATE_SCHEMA_VERSION,
    REQUIRED_FIELDS,
    CONDITIONALLY_REQUIRED_FIELDS,
    validate_state_entry,
    migrate_state_entry,
    validate_state_paths,
    enrich_state_entry,
    update_analysis_state,
    get_analysis_status,
)


def _minimal_completed_entry(**overrides):
    base = {
        "processed_at": datetime.now().isoformat(),
        "status": "completed",
        "transcript_path": "/tmp/test.json",
    }
    base.update(overrides)
    return base


def _minimal_pending_entry(**overrides):
    base = {
        "processed_at": datetime.now().isoformat(),
        "status": "pending",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# validate_state_entry
# ---------------------------------------------------------------------------
class TestValidateStateEntry:
    def test_valid_completed_entry(self):
        entry = _minimal_completed_entry()
        is_valid, errors = validate_state_entry(entry)
        assert is_valid
        assert errors == []

    def test_valid_pending_entry(self):
        entry = _minimal_pending_entry()
        is_valid, errors = validate_state_entry(entry)
        assert is_valid
        assert errors == []

    def test_missing_processed_at(self):
        entry = {"status": "completed", "transcript_path": "/tmp/t.json"}
        is_valid, errors = validate_state_entry(entry)
        assert not is_valid
        assert any("processed_at" in e for e in errors)

    def test_missing_status(self):
        entry = {"processed_at": datetime.now().isoformat()}
        is_valid, errors = validate_state_entry(entry)
        assert not is_valid
        assert any("status" in e for e in errors)

    def test_invalid_status_value(self):
        entry = {
            "processed_at": datetime.now().isoformat(),
            "status": "bogus",
        }
        is_valid, errors = validate_state_entry(entry)
        assert not is_valid
        assert any("Invalid status" in e for e in errors)

    def test_completed_missing_transcript_path(self):
        entry = {
            "processed_at": datetime.now().isoformat(),
            "status": "completed",
        }
        is_valid, errors = validate_state_entry(entry)
        assert not is_valid
        assert any("transcript_path" in e for e in errors)

    def test_failed_entry_does_not_require_transcript_path(self):
        entry = {
            "processed_at": datetime.now().isoformat(),
            "status": "failed",
        }
        is_valid, errors = validate_state_entry(entry)
        assert is_valid

    def test_invalid_processed_at_format(self):
        entry = {
            "processed_at": "not-a-date",
            "status": "pending",
        }
        is_valid, errors = validate_state_entry(entry)
        assert not is_valid
        assert any("processed_at format" in e for e in errors)

    def test_invalid_analysis_status(self):
        entry = _minimal_completed_entry(analysis_status="banana")
        is_valid, errors = validate_state_entry(entry)
        assert not is_valid
        assert any("analysis_status" in e for e in errors)

    def test_valid_analysis_status_values(self):
        for status in ("completed", "partial", "failed", "not_started"):
            entry = _minimal_completed_entry(analysis_status=status)
            is_valid, _ = validate_state_entry(entry)
            assert is_valid, f"Expected valid for analysis_status={status}"

    def test_invalid_analysis_timestamp(self):
        entry = _minimal_completed_entry(analysis_timestamp="nope")
        is_valid, errors = validate_state_entry(entry)
        assert not is_valid
        assert any("analysis_timestamp" in e for e in errors)

    def test_modules_run_not_subset_of_requested(self):
        entry = _minimal_completed_entry(
            analysis_modules_requested=["stats"],
            analysis_modules_run=["stats", "sentiment"],
        )
        is_valid, errors = validate_state_entry(entry)
        assert not is_valid
        assert any("subset" in e for e in errors)

    def test_modules_run_subset_valid(self):
        entry = _minimal_completed_entry(
            analysis_modules_requested=["stats", "sentiment"],
            analysis_modules_run=["stats"],
        )
        is_valid, _ = validate_state_entry(entry)
        assert is_valid

    def test_modules_not_lists_error(self):
        entry = _minimal_completed_entry(
            analysis_modules_requested="stats",
            analysis_modules_run="stats",
        )
        is_valid, errors = validate_state_entry(entry)
        assert not is_valid
        assert any("must be lists" in e for e in errors)


# ---------------------------------------------------------------------------
# migrate_state_entry
# ---------------------------------------------------------------------------
class TestMigrateStateEntry:
    def test_adds_default_fields(self):
        entry = {
            "processed_at": datetime.now().isoformat(),
            "status": "pending",
        }
        migrated = migrate_state_entry(entry)
        assert "analysis_completed" in migrated
        assert migrated["analysis_completed"] is False
        assert "last_updated" in migrated
        assert migrated["analysis_modules_requested"] == []
        assert migrated["analysis_modules_run"] == []
        assert migrated["analysis_modules_failed"] == []
        assert migrated["analysis_errors"] == []
        assert migrated["analysis_status"] == "not_started"

    def test_preserves_existing_fields(self):
        entry = _minimal_completed_entry(
            analysis_completed=True,
            analysis_status="completed",
            analysis_modules_requested=["stats"],
            analysis_modules_run=["stats"],
        )
        migrated = migrate_state_entry(entry)
        assert migrated["analysis_completed"] is True
        assert migrated["analysis_status"] == "completed"
        assert migrated["analysis_modules_requested"] == ["stats"]

    def test_infers_completed_status_from_flag(self):
        entry = {
            "processed_at": datetime.now().isoformat(),
            "status": "completed",
            "transcript_path": "/tmp/t.json",
            "analysis_completed": True,
        }
        migrated = migrate_state_entry(entry)
        assert migrated["analysis_status"] == "completed"

    def test_infers_partial_status_from_modules(self):
        entry = {
            "processed_at": datetime.now().isoformat(),
            "status": "completed",
            "transcript_path": "/tmp/t.json",
            "analysis_modules_requested": ["stats", "sentiment"],
            "analysis_modules_run": ["stats"],
        }
        migrated = migrate_state_entry(entry)
        assert migrated["analysis_status"] == "partial"

    def test_does_not_mutate_original(self):
        entry = {"processed_at": datetime.now().isoformat(), "status": "pending"}
        original_keys = set(entry.keys())
        migrate_state_entry(entry)
        assert set(entry.keys()) == original_keys


# ---------------------------------------------------------------------------
# validate_state_paths
# ---------------------------------------------------------------------------
class TestValidateStatePaths:
    def test_existing_paths_valid(self, tmp_path):
        transcript = tmp_path / "test.json"
        transcript.write_text("{}")
        entry = {
            "transcript_path": str(transcript),
        }
        is_valid, errors = validate_state_paths(entry)
        assert is_valid
        assert errors == []

    def test_nonexistent_path_error(self):
        entry = {"transcript_path": "/nonexistent/path.json"}
        is_valid, errors = validate_state_paths(entry)
        assert not is_valid
        assert any("does not exist" in e for e in errors)

    def test_none_path_ignored(self):
        entry = {"transcript_path": None, "mp3_path": None}
        is_valid, errors = validate_state_paths(entry)
        assert is_valid

    def test_empty_entry(self):
        is_valid, errors = validate_state_paths({})
        assert is_valid


# ---------------------------------------------------------------------------
# enrich_state_entry
# ---------------------------------------------------------------------------
class TestEnrichStateEntry:
    def test_adds_last_updated(self):
        entry = _minimal_pending_entry()
        enriched = enrich_state_entry(entry, "/tmp/test.json")
        assert "last_updated" in enriched
        datetime.fromisoformat(enriched["last_updated"])

    def test_does_not_mutate_original(self):
        entry = _minimal_pending_entry()
        original_keys = set(entry.keys())
        enrich_state_entry(entry, "/tmp/test.json")
        assert set(entry.keys()) == original_keys


# ---------------------------------------------------------------------------
# update_analysis_state
# ---------------------------------------------------------------------------
class TestUpdateAnalysisState:
    def test_completed_run(self):
        entry = _minimal_completed_entry()
        results = {
            "selected_modules": ["stats", "sentiment"],
            "modules_run": ["stats", "sentiment"],
            "errors": [],
            "duration": 12.5,
        }
        updated = update_analysis_state(entry, results)
        assert updated["analysis_status"] == "completed"
        assert updated["analysis_completed"] is True
        assert updated["analysis_duration_seconds"] == 12.5
        assert updated["analysis_modules_requested"] == ["stats", "sentiment"]
        assert updated["analysis_modules_run"] == ["stats", "sentiment"]
        assert updated["analysis_modules_failed"] == []

    def test_partial_run(self):
        entry = _minimal_completed_entry()
        results = {
            "selected_modules": ["stats", "sentiment"],
            "modules_run": ["stats"],
            "errors": ["sentiment failed: timeout"],
            "duration": 5.0,
        }
        updated = update_analysis_state(entry, results)
        assert updated["analysis_status"] == "partial"
        assert updated["analysis_completed"] is False
        assert "sentiment" in updated["analysis_modules_failed"]

    def test_failed_run(self):
        entry = _minimal_completed_entry()
        results = {
            "selected_modules": ["stats"],
            "modules_run": [],
            "errors": ["stats crashed"],
            "duration": 1.0,
        }
        updated = update_analysis_state(entry, results)
        assert updated["analysis_status"] == "failed"
        assert updated["analysis_completed"] is False

    def test_no_modules_requested(self):
        entry = _minimal_completed_entry()
        results = {"selected_modules": [], "modules_run": [], "errors": []}
        updated = update_analysis_state(entry, results)
        assert updated["analysis_status"] == "not_started"

    def test_does_not_mutate_original(self):
        entry = _minimal_completed_entry()
        original_keys = set(entry.keys())
        update_analysis_state(
            entry, {"selected_modules": ["s"], "modules_run": ["s"], "errors": []}
        )
        assert set(entry.keys()) == original_keys

    def test_timestamp_set(self):
        entry = _minimal_completed_entry()
        results = {"selected_modules": ["s"], "modules_run": ["s"], "errors": []}
        updated = update_analysis_state(entry, results)
        assert updated["analysis_timestamp"] is not None
        datetime.fromisoformat(updated["analysis_timestamp"])


# ---------------------------------------------------------------------------
# get_analysis_status
# ---------------------------------------------------------------------------
class TestGetAnalysisStatus:
    def test_not_started(self):
        entry = _minimal_pending_entry()
        status = get_analysis_status(entry)
        assert status["status"] == "not_started"
        assert status["completed"] is False
        assert status["modules_requested"] == []
        assert status["modules_pending"] == []

    def test_completed(self):
        entry = _minimal_completed_entry(
            analysis_status="completed",
            analysis_completed=True,
            analysis_modules_requested=["stats"],
            analysis_modules_run=["stats"],
            analysis_modules_failed=[],
            analysis_errors=[],
            analysis_duration_seconds=3.0,
            analysis_timestamp=datetime.now().isoformat(),
        )
        status = get_analysis_status(entry)
        assert status["status"] == "completed"
        assert status["completed"] is True
        assert status["has_errors"] is False
        assert status["error_count"] == 0
        assert status["modules_pending"] == []

    def test_partial_with_pending(self):
        entry = _minimal_completed_entry(
            analysis_status="partial",
            analysis_completed=False,
            analysis_modules_requested=["stats", "sentiment", "emotion"],
            analysis_modules_run=["stats"],
            analysis_modules_failed=["sentiment"],
            analysis_errors=["sentiment: timeout"],
        )
        status = get_analysis_status(entry)
        assert status["status"] == "partial"
        assert status["modules_pending"] == ["emotion"]
        assert status["has_errors"] is True
        assert status["error_count"] == 1

    def test_returns_all_expected_keys(self):
        entry = _minimal_pending_entry()
        status = get_analysis_status(entry)
        expected_keys = {
            "status",
            "modules_requested",
            "modules_run",
            "modules_failed",
            "modules_pending",
            "has_errors",
            "error_count",
            "duration_seconds",
            "timestamp",
            "completed",
        }
        assert set(status.keys()) == expected_keys
