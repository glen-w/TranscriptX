"""
Fixtures for state file recovery regression tests.

This module provides fixtures for testing state file recovery, including
corrupt JSON files, backup chains, and concurrent writer scenarios.
"""

import json

import pytest


@pytest.fixture
def fixture_corrupt_json(tmp_path, monkeypatch):
    """
    Create corrupt JSON file with syntax errors.

    Returns:
        Dict with corrupt state file path
    """
    state_file = tmp_path / "processing_state.json"

    # Create corrupt JSON (missing closing brace, invalid syntax)
    corrupt_content = """{
    "processed_files": {
        "test_key": {
            "transcript_path": "/path/to/file.json",
            "status": "processed"
        }
    }
    // Missing closing brace"""

    state_file.write_text(corrupt_content)
    monkeypatch.setattr(
        "transcriptx.cli.processing_state.PROCESSING_STATE_FILE", state_file
    )

    return {
        "state_file": str(state_file),
        "corrupt_content": corrupt_content,
    }


@pytest.fixture
def fixture_corrupt_json_missing_fields(tmp_path, monkeypatch):
    """
    Create JSON file missing required fields.

    Returns:
        Dict with state file missing fields
    """
    state_file = tmp_path / "processing_state.json"

    # JSON with missing "processed_files" key
    invalid_content = """{
    "last_updated": "2024-01-15T10:00:00Z"
}"""

    state_file.write_text(invalid_content)
    monkeypatch.setattr(
        "transcriptx.cli.processing_state.PROCESSING_STATE_FILE", state_file
    )

    return {
        "state_file": str(state_file),
        "invalid_content": invalid_content,
    }


@pytest.fixture
def fixture_corrupt_json_invalid_types(tmp_path, monkeypatch):
    """
    Create JSON file with wrong data types.

    Returns:
        Dict with state file with invalid types
    """
    state_file = tmp_path / "processing_state.json"

    # JSON with wrong types (processed_files should be dict, not list)
    invalid_content = """{
    "processed_files": [
        {"transcript_path": "/path/to/file.json"}
    ]
}"""

    state_file.write_text(invalid_content)
    monkeypatch.setattr(
        "transcriptx.cli.processing_state.PROCESSING_STATE_FILE", state_file
    )

    return {
        "state_file": str(state_file),
        "invalid_content": invalid_content,
    }


@pytest.fixture
def fixture_backup_chain(tmp_path, monkeypatch):
    """
    Create chain of backup files for recovery testing.

    Returns:
        Dict with state file and backup files
    """
    state_file = tmp_path / "processing_state.json"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # Create multiple backups with different timestamps
    backups = []
    for i in range(3):
        backup_file = backup_dir / f"processing_state.json.backup.{i}"
        backup_data = {
            "processed_files": {
                f"file_{i}": {
                    "transcript_path": f"/path/to/file_{i}.json",
                    "status": "processed",
                    "last_successful_run": f"2024-01-{15+i:02d}T10:00:00Z",
                }
            }
        }
        backup_file.write_text(json.dumps(backup_data, indent=2))
        backups.append(
            {
                "path": str(backup_file),
                "data": backup_data,
                "index": i,
            }
        )

    # Create corrupt main file
    state_file.write_text("{ invalid json }")
    monkeypatch.setattr(
        "transcriptx.cli.processing_state.PROCESSING_STATE_FILE", state_file
    )

    # Note: Backup system uses timestamped filenames, not indexed backups
    # The fixture creates backups with predictable names for testing

    return {
        "state_file": str(state_file),
        "backups": backups,
        "backup_dir": str(backup_dir),
    }


@pytest.fixture
def fixture_concurrent_writers(tmp_path, monkeypatch):
    """
    Setup for concurrent writer tests.

    Returns:
        Dict with state file and lock file paths
    """
    state_file = tmp_path / "processing_state.json"
    lock_file = state_file.with_suffix(state_file.suffix + ".lock")

    # Create initial state
    initial_state = {
        "processed_files": {
            "initial_file": {
                "transcript_path": "/path/to/initial.json",
                "status": "processed",
            }
        }
    }
    state_file.write_text(json.dumps(initial_state, indent=2))

    monkeypatch.setattr(
        "transcriptx.cli.processing_state.PROCESSING_STATE_FILE", state_file
    )

    return {
        "state_file": str(state_file),
        "lock_file": str(lock_file),
        "initial_state": initial_state,
    }
