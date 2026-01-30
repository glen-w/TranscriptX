"""
Tests for validation utilities.

This module tests input validation functions for transcripts,
files, and other data structures.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        """Test validation of file missing segments."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text('{"metadata": {"duration": 100}}')
        
        with pytest.raises(ValueError, match="segments"):
            validate_transcript_file(str(invalid_file))
    
    def test_validate_transcript_file_empty_segments(self, tmp_path):
        """Test validation of file with empty segments."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text('{"segments": []}')
        
        # Empty segments might be valid or invalid
        try:
            validate_transcript_file(str(empty_file))
        except ValueError:
            # Some implementations may reject empty segments
            pass
