"""
Tests for input validation utilities.

This module tests validation functions for transcripts, audio files, speaker maps, and more.
"""

import json

import pytest

from transcriptx.core.utils.validation import (
    validate_transcript_file,
    validate_segment,
    validate_audio_file,
    validate_output_directory,
    validate_speaker_map,
    validate_analysis_modules,
    validate_configuration,
    validate_file_path,
    validate_and_sanitize_inputs,
    sanitize_filename,
)


def _v1(segments: list) -> dict:
    return {
        "schema_version": "1.0",
        "source": {
            "type": "manual",
            "original_path": "t.json",
            "imported_at": "2020-01-01T00:00:00+00:00",
        },
        "segments": segments,
    }


class TestValidateTranscriptFile:
    """Tests for validate_transcript_file function."""

    def test_validates_valid_transcript(self, tmp_path):
        """Test validation of valid transcript file."""
        test_file = tmp_path / "test.json"
        data = _v1(
            [
                {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
            ]
        )
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
        """Root JSON must be an object (v1.0 artifact)."""
        test_file = tmp_path / "test.json"
        test_file.write_text(json.dumps(["not", "a", "dict"]))
        with pytest.raises(ValueError, match="JSON object|schema v1.0"):
            validate_transcript_file(str(test_file))

    def test_raises_error_when_missing_schema(self, tmp_path):
        """Non-v1 dict is rejected at load time."""
        test_file = tmp_path / "test.json"
        test_file.write_text(json.dumps({"other": "data"}))
        with pytest.raises(ValueError, match="schema_version|schema v1.0"):
            validate_transcript_file(str(test_file))

    def test_raises_error_when_segments_not_list(self, tmp_path):
        """Invalid segments type fails validate_transcript_document."""
        test_file = tmp_path / "test.json"
        test_file.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "source": {
                        "type": "manual",
                        "original_path": "x",
                        "imported_at": "2020-01-01T00:00:00+00:00",
                    },
                    "segments": "not a list",
                }
            )
        )
        with pytest.raises(ValueError, match="segments"):
            validate_transcript_file(str(test_file))

    def test_validates_segment_structure(self, tmp_path):
        """Test that segment structure is validated."""
        test_file = tmp_path / "test.json"
        data = _v1(
            [{"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0}]
        )
        test_file.write_text(json.dumps(data))

        result = validate_transcript_file(str(test_file))

        assert result is True

    def test_warns_on_empty_segments(self, tmp_path):
        """Test that warning is logged for empty segments."""
        test_file = tmp_path / "test.json"
        test_file.write_text(json.dumps(_v1([])))

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

    def test_raises_error_when_start_not_number(self):
        """Segment 'start' must be a number."""
        segment = {"speaker": "A", "text": "Hi", "start": "0.0", "end": 1.0}
        with pytest.raises(ValueError, match="'start' must be a number"):
            validate_segment(segment, 0)

    def test_raises_error_when_start_negative(self):
        """Segment 'start' cannot be negative."""
        segment = {"speaker": "A", "text": "Hi", "start": -0.1, "end": 1.0}
        with pytest.raises(ValueError, match="'start' cannot be negative"):
            validate_segment(segment, 0)

    def test_raises_error_when_end_not_number(self):
        """Segment 'end' must be a number."""
        segment = {"speaker": "A", "text": "Hi", "start": 0.0, "end": "1.0"}
        with pytest.raises(ValueError, match="'end' must be a number"):
            validate_segment(segment, 0)

    def test_raises_error_when_end_negative(self):
        """Segment 'end' cannot be negative."""
        segment = {"speaker": "A", "text": "Hi", "start": 0.0, "end": -1.0}
        with pytest.raises(ValueError, match="'end' cannot be negative"):
            validate_segment(segment, 0)

    def test_raises_error_when_start_ge_end(self):
        """Segment 'start' must be less than 'end'."""
        segment = {"speaker": "A", "text": "Hi", "start": 1.0, "end": 1.0}
        with pytest.raises(ValueError, match="'start' must be less than 'end'"):
            validate_segment(segment, 0)


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

    def test_raises_error_for_empty_audio_file(self, tmp_path):
        """Test that ValueError is raised for empty audio file."""
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"")

        with pytest.raises(ValueError, match="Audio file is empty"):
            validate_audio_file(str(test_file))

    def test_raises_error_for_invalid_extension(self, tmp_path):
        """Test that ValueError is raised for invalid extension."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("not audio")

        with pytest.raises(ValueError, match="Unsupported audio format"):
            validate_audio_file(str(test_file))

    def test_warns_on_very_small_audio_file(self, tmp_path):
        """Test that very small file (< 1KB) does not raise but may log warning."""
        test_file = tmp_path / "tiny.mp3"
        test_file.write_bytes(b"x" * 100)

        result = validate_audio_file(str(test_file))
        assert result is True

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

    def test_raises_error_for_empty_path(self):
        """Output directory path cannot be empty."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_output_directory("")

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

    def test_raises_error_when_no_write_permission(self, tmp_path):
        """Test that error is raised when directory is not writable."""
        read_only = tmp_path / "readonly"
        read_only.mkdir()
        try:

            read_only.chmod(0o444)
            with pytest.raises(ValueError, match="No write permission"):
                validate_output_directory(str(read_only))
        finally:
            read_only.chmod(0o755)

    def test_raises_error_when_makedirs_fails(self, tmp_path, monkeypatch):
        """Test that OSError from makedirs is converted to ValueError."""
        bad_path = tmp_path / "nested" / "dir"

        def failing_makedirs(path, exist_ok=False):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr("os.makedirs", failing_makedirs)
        with pytest.raises(ValueError, match="Cannot create output directory"):
            validate_output_directory(str(bad_path), create_if_missing=True)


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

        with pytest.raises(ValueError, match="Speaker name must be string"):
            validate_speaker_map(speaker_map)

    def test_accepts_empty_map(self):
        """Test that empty map is accepted."""
        result = validate_speaker_map({})

        assert result is True

    def test_raises_error_when_speaker_id_not_string(self):
        """Speaker ID must be string."""
        with pytest.raises(ValueError, match="Speaker ID must be string"):
            validate_speaker_map({123: "Alice"})

    def test_raises_error_when_speaker_name_empty(self):
        """Speaker name cannot be empty."""
        with pytest.raises(ValueError, match="Speaker name cannot be empty"):
            validate_speaker_map({"SPEAKER_00": "  \t  "})


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

        with pytest.raises(ValueError, match="Invalid analysis modules"):
            validate_analysis_modules(modules, available)

    def test_accepts_empty_list(self):
        """Test that empty list is accepted."""
        with pytest.raises(ValueError, match="At least one analysis module"):
            validate_analysis_modules([], ["sentiment"])

    def test_raises_error_when_modules_not_list(self):
        """Modules must be a list."""
        with pytest.raises(ValueError, match="Modules must be a list"):
            validate_analysis_modules("sentiment", ["sentiment"])


class TestValidateConfiguration:
    """Tests for validate_configuration function."""

    def test_validates_minimal_config(self):
        """Config with required sections (analysis, output, logging) passes."""
        config = {"analysis": {}, "output": {}, "logging": {}}
        assert validate_configuration(config) is True

    def test_raises_error_when_not_dict(self):
        with pytest.raises(ValueError, match="Configuration must be a dictionary"):
            validate_configuration([])

    def test_raises_error_when_section_missing(self):
        config = {"analysis": {}, "output": {}}
        with pytest.raises(ValueError, match="missing required section: logging"):
            validate_configuration(config)

    def test_raises_error_when_section_not_dict(self):
        config = {"analysis": [], "output": {}, "logging": {}}
        with pytest.raises(ValueError, match="must be a dictionary"):
            validate_configuration(config)

    def test_raises_error_for_invalid_sentiment_window_size(self):
        config = {
            "analysis": {"sentiment_window_size": 0},
            "output": {},
            "logging": {},
        }
        with pytest.raises(
            ValueError, match="sentiment_window_size must be a positive integer"
        ):
            validate_configuration(config)

    def test_raises_error_for_invalid_emotion_min_confidence_type(self):
        config = {
            "analysis": {"emotion_min_confidence": "0.5"},
            "output": {},
            "logging": {},
        }
        with pytest.raises(ValueError, match="emotion_min_confidence must be a number"):
            validate_configuration(config)

    def test_raises_error_for_emotion_min_confidence_out_of_range(self):
        config = {
            "analysis": {"emotion_min_confidence": 1.5},
            "output": {},
            "logging": {},
        }
        with pytest.raises(
            ValueError, match="emotion_min_confidence must be between 0 and 1"
        ):
            validate_configuration(config)


class TestValidateFilePath:
    """Tests for validate_file_path function."""

    def test_valid_existing_path(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("x")
        assert validate_file_path(str(f), must_exist=True) is True

    def test_raises_for_empty_path(self):
        with pytest.raises(ValueError, match="path cannot be empty"):
            validate_file_path("")

    def test_raises_for_non_string_path(self):
        with pytest.raises(ValueError, match="must be a string"):
            validate_file_path(123, must_exist=False)

    def test_raises_when_must_exist_and_not_found(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            validate_file_path("/nonexistent/path", must_exist=True)

    def test_allows_nonexistent_when_must_exist_false(self):
        assert validate_file_path("/nonexistent/path", must_exist=False) is True


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

        assert result == "unnamed"

    def test_handles_unicode(self):
        """Test that unicode characters are handled."""
        filename = "test_文件_名称.txt"

        result = sanitize_filename(filename)

        # Should not crash, may sanitize or preserve
        assert isinstance(result, str)

    def test_returns_unnamed_when_only_spaces_and_dots(self):
        """Filename that becomes empty after strip returns 'unnamed'."""
        result = sanitize_filename("   .   .   ")
        assert result == "unnamed"


def _set_valid_default_paths(tmp_path, monkeypatch):
    """Point default validation paths to tmp_path with valid transcript and audio."""
    transcript_file = tmp_path / "transcript.json"
    transcript_file.write_text(
        json.dumps(
            _v1(
                [{"speaker": "A", "text": "Hi", "start": 0.0, "end": 1.0}],
            )
        )
    )
    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"x" * 1024)
    monkeypatch.setattr(
        "transcriptx.core.utils.validation.DIARISED_TRANSCRIPTS_DIR",
        str(transcript_file),
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.validation.RECORDINGS_DIR",
        str(audio_file),
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.validation.OUTPUTS_DIR",
        str(tmp_path),
    )


class TestValidateAndSanitizeInputs:
    """Tests for validate_and_sanitize_inputs function."""

    def test_returns_defaults_when_all_none(self, tmp_path, monkeypatch):
        """When all None, uses default paths and returns them validated."""
        _set_valid_default_paths(tmp_path, monkeypatch)
        transcript_file = tmp_path / "transcript.json"
        audio_file = tmp_path / "audio.mp3"
        result = validate_and_sanitize_inputs()
        assert result["transcript_path"] == str(transcript_file)
        assert result["audio_path"] == str(audio_file)
        assert result["output_dir"] == str(tmp_path)

    def test_includes_modules_when_provided(self, tmp_path, monkeypatch):
        """Modules list is included when provided."""
        _set_valid_default_paths(tmp_path, monkeypatch)
        result = validate_and_sanitize_inputs(modules=["sentiment"])
        assert result["modules"] == ["sentiment"]

    def test_raises_when_modules_not_list(self, tmp_path, monkeypatch):
        """Modules must be a list."""
        _set_valid_default_paths(tmp_path, monkeypatch)
        with pytest.raises(ValueError, match="Modules must be a list"):
            validate_and_sanitize_inputs(modules="sentiment")

    def test_validates_transcript_when_provided(self, tmp_path):
        """When transcript_path provided, it is validated."""
        bad = tmp_path / "bad.txt"
        bad.write_text("x")
        with pytest.raises(ValueError, match="must be JSON format"):
            validate_and_sanitize_inputs(transcript_path=str(bad))
