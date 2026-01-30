"""
Tests for input validation utilities.

This module tests validation functions for transcripts, audio files, speaker maps, and more.
"""

import json
from pathlib import Path

import pytest

from transcriptx.core.utils.validation import (
    validate_transcript_file,
    validate_segment,
    validate_audio_file,
    validate_output_directory,
    validate_speaker_map,
    validate_analysis_modules,
    sanitize_filename,
)


class TestValidateTranscriptFile:
    """Tests for validate_transcript_file function."""
    
    def test_validates_valid_transcript(self, tmp_path):
        """Test validation of valid transcript file."""
        test_file = tmp_path / "test.json"
        data = {
            "segments": [
                {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0}
            ]
        }
        test_file.write_text(json.dumps(data))
        
        result = validate_transcript_file(str(test_file))
        
        assert result is True
    
    def test_raises_error_for_empty_path(self):
        """Test that ValueError is raised for empty path."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_transcript_file("")
    
    def test_raises_error_for_nonexistent_file(self):
        """Test that FileNotFoundError is raised for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            validate_transcript_file("/nonexistent/file.json")
    
    def test_raises_error_for_non_json_file(self, tmp_path):
        """Test that ValueError is raised for non-JSON file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("not json")
        
        with pytest.raises(ValueError, match="must be JSON format"):
            validate_transcript_file(str(test_file))
    
    def test_raises_error_for_invalid_json(self, tmp_path):
        """Test that ValueError is raised for invalid JSON."""
        test_file = tmp_path / "test.json"
        test_file.write_text("invalid json content")
        
        with pytest.raises(ValueError, match="Invalid JSON"):
            validate_transcript_file(str(test_file))
    
    def test_raises_error_when_not_dict(self, tmp_path):
        """Test that ValueError is raised when file is not a dict."""
        test_file = tmp_path / "test.json"
        test_file.write_text(json.dumps(["not", "a", "dict"]))
        
        with pytest.raises(ValueError, match="must contain a JSON object"):
            validate_transcript_file(str(test_file))
    
    def test_raises_error_when_missing_segments(self, tmp_path):
        """Test that ValueError is raised when 'segments' key is missing."""
        test_file = tmp_path / "test.json"
        test_file.write_text(json.dumps({"other": "data"}))
        
        with pytest.raises(ValueError, match="must contain 'segments' key"):
            validate_transcript_file(str(test_file))
    
    def test_raises_error_when_segments_not_list(self, tmp_path):
        """Test that ValueError is raised when segments is not a list."""
        test_file = tmp_path / "test.json"
        test_file.write_text(json.dumps({"segments": "not a list"}))
        
        with pytest.raises(ValueError, match="must be a list"):
            validate_transcript_file(str(test_file))
    
    def test_validates_segment_structure(self, tmp_path):
        """Test that segment structure is validated."""
        test_file = tmp_path / "test.json"
        data = {
            "segments": [
                {"speaker": "SPEAKER_00", "text": "Hello"}
            ]
        }
        test_file.write_text(json.dumps(data))
        
        result = validate_transcript_file(str(test_file))
        
        assert result is True
    
    def test_warns_on_empty_segments(self, tmp_path):
        """Test that warning is logged for empty segments."""
        test_file = tmp_path / "test.json"
        test_file.write_text(json.dumps({"segments": []}))
        
        # Should not raise error, just warn
        result = validate_transcript_file(str(test_file))
        assert result is True


class TestValidateSegment:
    """Tests for validate_segment function."""
    
    def test_validates_valid_segment(self):
        """Test validation of valid segment."""
        segment = {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0}
        
        result = validate_segment(segment, 0)
        
        assert result is True
    
    def test_raises_error_when_not_dict(self):
        """Test that ValueError is raised when segment is not a dict."""
        with pytest.raises(ValueError, match="must be a dictionary"):
            validate_segment(["not", "a", "dict"], 0)
    
    def test_raises_error_when_missing_text(self):
        """Test that ValueError is raised when 'text' field is missing."""
        segment = {"speaker": "SPEAKER_00"}
        
        with pytest.raises(ValueError, match="missing required field: text"):
            validate_segment(segment, 0)
    
    def test_raises_error_when_missing_speaker(self):
        """Test that ValueError is raised when 'speaker' field is missing."""
        segment = {"text": "Hello"}
        
        with pytest.raises(ValueError, match="missing required field: speaker"):
            validate_segment(segment, 0)
    
    def test_raises_error_when_text_not_string(self):
        """Test that ValueError is raised when text is not a string."""
        segment = {"speaker": "SPEAKER_00", "text": 123}
        
        with pytest.raises(ValueError, match="'text' must be a string"):
            validate_segment(segment, 0)
    
    def test_raises_error_when_speaker_not_string(self):
        """Test that ValueError is raised when speaker is not a string."""
        segment = {"speaker": 123, "text": "Hello"}
        
        with pytest.raises(ValueError, match="'speaker' must be a string"):
            validate_segment(segment, 0)
    
    def test_warns_on_empty_text(self):
        """Test that warning is logged for empty text."""
        segment = {"speaker": "SPEAKER_00", "text": "   "}
        
        # Should not raise error, just warn
        result = validate_segment(segment, 0)
        assert result is True


class TestValidateAudioFile:
    """Tests for validate_audio_file function."""
    
    def test_validates_valid_audio_file(self, tmp_path):
        """Test validation of valid audio file."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")
        
        result = validate_audio_file(str(test_file))
        
        assert result is True
    
    def test_raises_error_for_empty_path(self):
        """Test that ValueError is raised for empty path."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_audio_file("")
    
    def test_raises_error_for_nonexistent_file(self):
        """Test that FileNotFoundError is raised for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            validate_audio_file("/nonexistent/file.mp3")
    
    def test_raises_error_for_invalid_extension(self, tmp_path):
        """Test that ValueError is raised for invalid extension."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("not audio")
        
        with pytest.raises(ValueError, match="must be an audio file"):
            validate_audio_file(str(test_file))
    
    def test_accepts_valid_extensions(self, tmp_path):
        """Test that valid audio extensions are accepted."""
        valid_extensions = [".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"]
        
        for ext in valid_extensions:
            test_file = tmp_path / f"test{ext}"
            test_file.write_text("fake audio")
            
            result = validate_audio_file(str(test_file))
            assert result is True


class TestValidateOutputDirectory:
    """Tests for validate_output_directory function."""
    
    def test_validates_existing_directory(self, tmp_path):
        """Test validation of existing directory."""
        test_dir = tmp_path / "outputs"
        test_dir.mkdir()
        
        result = validate_output_directory(str(test_dir))
        
        assert result is True
    
    def test_creates_directory_if_missing(self, tmp_path):
        """Test that directory is created if missing and create_if_missing is True."""
        test_dir = tmp_path / "outputs"
        
        result = validate_output_directory(str(test_dir), create_if_missing=True)
        
        assert result is True
        assert test_dir.exists()
    
    def test_raises_error_when_not_created(self, tmp_path):
        """Test that error is raised when directory doesn't exist and create_if_missing is False."""
        test_dir = tmp_path / "nonexistent"
        
        with pytest.raises(ValueError, match="does not exist"):
            validate_output_directory(str(test_dir), create_if_missing=False)
    
    def test_raises_error_for_file_instead_of_directory(self, tmp_path):
        """Test that error is raised when path is a file."""
        test_file = tmp_path / "file.txt"
        test_file.write_text("not a directory")
        
        with pytest.raises(ValueError, match="is not a directory"):
            validate_output_directory(str(test_file))


class TestValidateSpeakerMap:
    """Tests for validate_speaker_map function."""
    
    def test_validates_valid_speaker_map(self):
        """Test validation of valid speaker map."""
        speaker_map = {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}
        
        result = validate_speaker_map(speaker_map)
        
        assert result is True
    
    def test_raises_error_when_not_dict(self):
        """Test that ValueError is raised when speaker map is not a dict."""
        with pytest.raises(ValueError, match="must be a dictionary"):
            validate_speaker_map(["not", "a", "dict"])
    
    def test_raises_error_when_values_not_strings(self):
        """Test that ValueError is raised when values are not strings."""
        speaker_map = {"SPEAKER_00": 123}
        
        with pytest.raises(ValueError, match="must be strings"):
            validate_speaker_map(speaker_map)
    
    def test_accepts_empty_map(self):
        """Test that empty map is accepted."""
        result = validate_speaker_map({})
        
        assert result is True


class TestValidateAnalysisModules:
    """Tests for validate_analysis_modules function."""
    
    def test_validates_valid_modules(self):
        """Test validation of valid modules."""
        modules = ["sentiment", "emotion", "ner"]
        available = ["sentiment", "emotion", "ner", "stats"]
        
        result = validate_analysis_modules(modules, available)
        
        assert result is True
    
    def test_raises_error_for_invalid_module(self):
        """Test that ValueError is raised for invalid module."""
        modules = ["sentiment", "invalid_module"]
        available = ["sentiment", "emotion"]
        
        with pytest.raises(ValueError, match="not available"):
            validate_analysis_modules(modules, available)
    
    def test_accepts_empty_list(self):
        """Test that empty list is accepted."""
        result = validate_analysis_modules([], ["sentiment"])
        
        assert result is True


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""
    
    def test_sanitizes_special_characters(self):
        """Test that special characters are sanitized."""
        filename = "test/file:name*.txt"
        
        result = sanitize_filename(filename)
        
        assert "/" not in result
        assert ":" not in result
        assert "*" not in result
    
    def test_preserves_valid_characters(self):
        """Test that valid characters are preserved."""
        filename = "test_file-name_123.txt"
        
        result = sanitize_filename(filename)
        
        assert "test_file-name_123.txt" in result or "test_file-name_123" in result
    
    def test_handles_empty_string(self):
        """Test that empty string is handled."""
        result = sanitize_filename("")
        
        assert result == ""
    
    def test_handles_unicode(self):
        """Test that unicode characters are handled."""
        filename = "test_文件_名称.txt"
        
        result = sanitize_filename(filename)
        
        # Should not crash, may sanitize or preserve
        assert isinstance(result, str)
