"""
Fixtures for path resolution regression tests.

This module provides fixtures for testing path resolution edge cases,
including ambiguous duplicates, relative vs absolute paths, stale state
pointers, and moved outputs.
"""

import json
from pathlib import Path
from typing import Dict

import pytest

from transcriptx.cli.processing_state import PROCESSING_STATE_FILE


@pytest.fixture
def fixture_ambiguous_duplicates(tmp_path):
    """
    Create multiple files with same basename in different directories.
    
    Returns:
        Dict with:
        - base_name: The common basename
        - files: List of file paths with same basename
        - expected_winner: Which file should be chosen (by strategy order)
    """
    base_name = "meeting_2024_01_15"
    
    # Create files in different directories
    # Use standard transcript directories for better compatibility
    from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR, OUTPUTS_DIR
    
    # Create test directories
    dir1 = tmp_path / "transcripts" / "dir1"
    dir2 = tmp_path / "transcripts" / "dir2"
    dir3 = tmp_path / "outputs" / "dir3"
    
    dir1.mkdir(parents=True, exist_ok=True)
    dir2.mkdir(parents=True, exist_ok=True)
    dir3.mkdir(parents=True, exist_ok=True)
    
    file1 = dir1 / f"{base_name}.json"
    file2 = dir2 / f"{base_name}.json"
    file3 = dir3 / f"{base_name}.json"
    
    # Create files with different content to verify which one is chosen
    file1.write_text(json.dumps({"source": "dir1", "segments": []}))
    file2.write_text(json.dumps({"source": "dir2", "segments": []}))
    file3.write_text(json.dumps({"source": "dir3", "segments": []}))
    
    return {
        "base_name": base_name,
        "files": [str(file1), str(file2), str(file3)],
        "directories": [str(dir1), str(dir2), str(dir3)],
        "expected_winner": str(file1),  # First in canonical order
    }


@pytest.fixture
def fixture_relative_vs_absolute(tmp_path):
    """
    Create mix of relative and absolute paths.
    
    Returns:
        Dict with relative and absolute paths to same file
    """
    test_file = tmp_path / "test_transcript.json"
    test_file.write_text(json.dumps({"segments": []}))
    
    # Change to a subdirectory to create relative path
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    
    relative_path = "../test_transcript.json"
    absolute_path = str(test_file.resolve())
    
    return {
        "file": str(test_file),
        "relative_path": relative_path,
        "absolute_path": absolute_path,
        "working_dir": str(subdir),
    }


@pytest.fixture
def fixture_stale_state_pointers(tmp_path, monkeypatch):
    """
    Create state file pointing to moved/deleted files.
    
    Returns:
        Dict with state file path and stale entries
    """
    state_file = tmp_path / "processing_state.json"
    
    # Create a file, then move it
    original_file = tmp_path / "original_transcript.json"
    original_file.write_text(json.dumps({"segments": []}))
    
    moved_file = tmp_path / "moved" / "transcript.json"
    moved_file.parent.mkdir()
    moved_file.write_text(original_file.read_text())
    original_file.unlink()  # Delete original
    
    # Create state file with stale pointer
    state_data = {
        "processed_files": {
            "test_key": {
                "transcript_path": str(original_file),  # Stale - file doesn't exist
                "status": "processed",
            }
        }
    }
    state_file.write_text(json.dumps(state_data))
    
    # Monkeypatch PROCESSING_STATE_FILE
    monkeypatch.setattr("transcriptx.cli.processing_state.PROCESSING_STATE_FILE", state_file)
    
    return {
        "state_file": str(state_file),
        "stale_transcript_path": str(original_file),
        "valid_moved_path": str(moved_file),
        "state_data": state_data,
    }


@pytest.fixture
def fixture_moved_outputs(tmp_path):
    """
    Create output directories that have been moved.
    
    Returns:
        Dict with original and moved output directories
    """
    original_output = tmp_path / "outputs" / "meeting_2024_01_15"
    original_output.mkdir(parents=True, exist_ok=True)
    
    # Create some files in original output
    sentiment_file = original_output / "sentiment" / "data" / "global_sentiment.json"
    sentiment_file.parent.mkdir(parents=True, exist_ok=True)
    sentiment_file.write_text(json.dumps({"sentiment": "positive"}))
    
    # Move the output directory
    moved_output = tmp_path / "archived" / "meeting_2024_01_15"
    moved_output.parent.mkdir(parents=True, exist_ok=True)
    
    # Copy files (simulating move)
    import shutil
    shutil.copytree(original_output, moved_output, dirs_exist_ok=True)
    shutil.rmtree(original_output)
    
    return {
        "original_path": str(original_output),
        "moved_path": str(moved_output),
        "base_name": "meeting_2024_01_15",
    }
