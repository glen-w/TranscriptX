"""
Tests for validation utilities.

This module tests input validation functions for transcripts,
files, and other data structures.
"""

import json

import pytest

from transcriptx.core.utils.validation import validate_transcript_file


class TestValidation:
    """Tests for validation utilities."""

    def test_validate_transcript_file_valid(self, temp_transcript_file):
        """Test validation of valid transcript file."""
        # Should not raise
        validate_transcript_file(str(temp_transcript_file))

    def test_validate_transcript_file_not_found(self, tmp_path):
        """Test validation of non-existent file."""
        non_existent = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            validate_transcript_file(str(non_existent))

    def test_validate_transcript_file_invalid_json(self, tmp_path):
        """Test validation of invalid JSON."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("not json")

        with pytest.raises((ValueError, json.JSONDecodeError)):
            validate_transcript_file(str(invalid_file))

    def test_validate_transcript_file_missing_segments(self, tmp_path):
        """Non-v1.0 artifacts are rejected (missing schema/source/segments)."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text('{"metadata": {"duration": 100}}')
        with pytest.raises(ValueError, match="schema_version|schema v1.0"):
            validate_transcript_file(str(invalid_file))

    def test_validate_transcript_file_empty_segments(self, tmp_path):
        """v1.0 artifact may have empty segments list."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "source": {
                        "type": "manual",
                        "original_path": "empty.json",
                        "imported_at": "2026-01-01T00:00:00Z",
                    },
                    "segments": [],
                }
            )
        )
        assert validate_transcript_file(str(empty_file)) is True
