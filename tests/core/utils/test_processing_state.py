"""
Unit tests for processing_state load/save (core state persistence).

Tests load_processing_state and save_processing_state with tmp paths and
mocked lock/backup so they run in default suite (no DB, no real lock).
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from transcriptx.core.utils.processing_state import (
    _is_uuid_format,
    is_file_processed,
    load_processing_state,
    migrate_processing_state_to_uuid_keys,
    save_processing_state,
)


@pytest.fixture
def state_file(tmp_path):
    """Temporary state file path."""
    return tmp_path / "processing_state.json"


def test_load_processing_state_nonexistent_returns_empty(state_file):
    """When state file does not exist, load returns empty processed_files dict."""
    assert not state_file.exists()
    with patch(
        "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE",
        state_file,
    ):
        result = load_processing_state(
            state_file=state_file,
            validate=False,
            skip_migration=True,
        )
    assert result == {"processed_files": {}}


def test_load_processing_state_valid_json_returns_parsed(state_file):
    """Load returns parsed JSON when file exists and is valid."""
    state_data = {
        "processed_files": {
            "uuid-1": {
                "transcript_path": "/path/to/transcript.json",
                "status": "completed",
            }
        }
    }
    state_file.write_text(json.dumps(state_data))

    with (
        patch(
            "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE",
            state_file,
        ),
        patch(
            "transcriptx.core.utils.file_lock.FileLock",
        ) as mock_lock_cls,
    ):
        mock_lock = mock_lock_cls.return_value
        mock_lock.acquired = True
        mock_lock.__enter__ = lambda self: self
        mock_lock.__exit__ = lambda self, *args: None
        result = load_processing_state(
            state_file=state_file,
            validate=False,
            skip_migration=True,
        )
    assert result == state_data


def test_save_processing_state_creates_file(state_file):
    """Save writes state JSON to the given path (with mocked lock and backup)."""
    state_data = {
        "processed_files": {
            "uuid-1": {
                "transcript_path": str(state_file.parent / "t.json"),
                "status": "completed",
            }
        }
    }
    state_file.parent.mkdir(parents=True, exist_ok=True)

    with (
        patch(
            "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE",
            state_file,
        ),
        patch(
            "transcriptx.core.utils.file_lock.FileLock",
        ) as mock_lock_cls,
        patch(
            "transcriptx.core.utils.state_backup.create_backup",
        ),
    ):
        mock_lock = mock_lock_cls.return_value
        mock_lock.acquired = True
        mock_lock.__enter__ = lambda self: self
        mock_lock.__exit__ = lambda self, *args: None
        save_processing_state(state_data, state_file)

    assert state_file.exists()
    loaded = json.loads(state_file.read_text(encoding="utf-8"))
    assert loaded == state_data


def test_load_save_roundtrip(state_file):
    """Roundtrip: save then load returns same data (mocked lock/backup)."""
    state_data = {
        "processed_files": {
            "uuid-a": {
                "transcript_path": "/a/transcript.json",
                "status": "completed",
                "output_dir": "/a/out",
            }
        }
    }
    state_file.parent.mkdir(parents=True, exist_ok=True)

    with (
        patch(
            "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE",
            state_file,
        ),
        patch(
            "transcriptx.core.utils.file_lock.FileLock",
        ) as mock_lock_cls,
        patch(
            "transcriptx.core.utils.state_backup.create_backup",
        ),
    ):
        mock_lock = mock_lock_cls.return_value
        mock_lock.acquired = True
        mock_lock.__enter__ = lambda self: self
        mock_lock.__exit__ = lambda self, *args: None
        save_processing_state(state_data, state_file)

        result = load_processing_state(
            state_file=state_file,
            validate=False,
            skip_migration=True,
        )

    assert result == state_data


def test_load_processing_state_locked_returns_empty(state_file):
    """When file exists but lock is not acquired, load returns empty processed_files."""
    state_file.write_text(json.dumps({"processed_files": {"k": {}}}))

    with (
        patch(
            "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE",
            state_file,
        ),
        patch(
            "transcriptx.core.utils.file_lock.FileLock",
        ) as mock_lock_cls,
    ):
        mock_lock = mock_lock_cls.return_value
        mock_lock.acquired = False
        mock_lock.__enter__ = lambda self: self
        mock_lock.__exit__ = lambda self, *args: None
        result = load_processing_state(
            state_file=state_file,
            validate=False,
            skip_migration=True,
        )

    assert result == {"processed_files": {}}


# ---- _is_uuid_format (used by migration and is_file_processed) ----


def test_is_uuid_format_valid_uuid():
    """_is_uuid_format returns True for valid UUID strings."""
    assert _is_uuid_format("550e8400-e29b-41d4-a716-446655440000") is True
    assert _is_uuid_format("00000000-0000-0000-0000-000000000000") is True


def test_is_uuid_format_invalid():
    """_is_uuid_format returns False for non-UUID keys."""
    assert _is_uuid_format("/path/to/transcript.json") is False
    assert _is_uuid_format("") is False
    assert _is_uuid_format("short") is False
    assert _is_uuid_format("550e8400-e29b-41d4-a716") is False  # too short


# ---- load with validate=True (no migration) ----


def test_load_processing_state_with_validate_true_valid_state(state_file):
    """Load with validate=True and valid state runs validation and returns state (no migration)."""
    state_data = {
        "processed_files": {
            "550e8400-e29b-41d4-a716-446655440000": {
                "transcript_path": "/path/to/transcript.json",
                "status": "completed",
            }
        }
    }
    state_file.write_text(json.dumps(state_data))
    with (
        patch(
            "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE",
            state_file,
        ),
        patch(
            "transcriptx.core.utils.file_lock.cleanup_stale_locks",
        ),
        patch(
            "transcriptx.core.utils.file_lock.FileLock",
        ) as mock_lock_cls,
        patch(
            "transcriptx.core.utils.state_utils.validate_processing_state",
            return_value={"valid": True, "errors": []},
        ),
    ):
        mock_lock = mock_lock_cls.return_value
        mock_lock.acquired = True
        mock_lock.__enter__ = lambda self: self
        mock_lock.__exit__ = lambda self, *args: None
        result = load_processing_state(
            state_file=state_file,
            validate=True,
            skip_migration=True,
        )
    assert result == state_data


def test_load_processing_state_corrupt_json_returns_empty(state_file):
    """Load with corrupt JSON and validate=False returns empty processed_files."""
    state_file.write_text("not valid json {")
    with (
        patch(
            "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE",
            state_file,
        ),
        patch(
            "transcriptx.core.utils.file_lock.cleanup_stale_locks",
        ),
        patch(
            "transcriptx.core.utils.file_lock.FileLock",
        ) as mock_lock_cls,
    ):
        mock_lock = mock_lock_cls.return_value
        mock_lock.acquired = True
        mock_lock.__enter__ = lambda self: self
        mock_lock.__exit__ = lambda self, *args: None
        result = load_processing_state(
            state_file=state_file,
            validate=False,
            skip_migration=True,
        )
    assert result == {"processed_files": {}}


# ---- is_file_processed (JSON fallback only, no DB) ----


def test_is_file_processed_with_state_by_audio_path(tmp_path):
    """is_file_processed returns True when state has matching audio_path (UUID key)."""
    state = {
        "processed_files": {
            "550e8400-e29b-41d4-a716-446655440000": {
                "audio_path": str(tmp_path / "audio.wav"),
                "status": "completed",
            }
        }
    }
    wav_path = tmp_path / "audio.wav"
    wav_path.touch()
    assert is_file_processed(wav_path, state=state) is True


def test_is_file_processed_with_state_by_filename(tmp_path):
    """is_file_processed returns True when state has entry with matching filename (path key)."""
    state = {
        "processed_files": {
            str(tmp_path / "other" / "audio.wav"): {
                "audio_path": str(tmp_path / "other" / "audio.wav"),
                "status": "completed",
            }
        }
    }
    # Query by same filename in different dir
    query_path = tmp_path / "subdir" / "audio.wav"
    query_path.parent.mkdir(parents=True, exist_ok=True)
    query_path.touch()
    assert is_file_processed(query_path, state=state) is True


def test_is_file_processed_not_processed(tmp_path):
    """is_file_processed returns False when state has no matching entry."""
    state = {"processed_files": {}}
    wav_path = tmp_path / "audio.wav"
    wav_path.touch()
    assert is_file_processed(wav_path, state=state) is False


# ---- migrate_processing_state_to_uuid_keys (no-op branches, no DB) ----


def test_migrate_processing_state_empty_returns_not_migrated(state_file):
    """migrate_processing_state_to_uuid_keys returns not migrated when state has no entries."""
    state_file.write_text(json.dumps({"processed_files": {}}))
    with (
        patch(
            "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE",
            state_file,
        ),
        patch(
            "transcriptx.core.utils.processing_state.load_processing_state",
            return_value={"processed_files": {}},
        ),
    ):
        result = migrate_processing_state_to_uuid_keys()
    assert result["migrated"] is False
    assert result.get("reason") == "No entries to migrate"
    assert result.get("entries_migrated", 0) == 0


def test_migrate_processing_state_already_uuid_keys_returns_not_migrated(state_file):
    """migrate_processing_state_to_uuid_keys returns not migrated when all keys are already UUIDs."""
    state_data = {
        "processed_files": {
            "550e8400-e29b-41d4-a716-446655440000": {
                "transcript_path": "/path/to/t.json",
                "status": "completed",
            }
        }
    }
    with (
        patch(
            "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE",
            state_file,
        ),
        patch(
            "transcriptx.core.utils.processing_state.load_processing_state",
            return_value=state_data,
        ),
    ):
        result = migrate_processing_state_to_uuid_keys()
    assert result["migrated"] is False
    assert "Already using UUID" in result.get("reason", "")
    assert result.get("entries_migrated", 0) == 0
