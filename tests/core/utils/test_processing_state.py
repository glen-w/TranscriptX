"""
Unit tests for processing_state load/save (core state persistence).

Tests load_processing_state and save_processing_state with tmp paths and
mocked lock/backup so they run in default suite (no DB, no real lock).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.core.utils.processing_state import (
    load_processing_state,
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
