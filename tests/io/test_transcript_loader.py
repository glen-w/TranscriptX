"""
Tests for transcript loading operations.

This module tests loading transcripts from various formats, edge cases,
and error handling.
"""

import json
from unittest.mock import patch

import pytest

from transcriptx.io.transcript_loader import (
    extract_speaker_map_from_transcript,
    load_segments,
    load_transcript,
    load_transcript_data,
)


class TestLoadSegments:
    """Tests for load_segments function."""

    def test_loads_segments_from_dict(self, tmp_path):
        """Test loading segments from dict with 'segments' key."""
        test_file = tmp_path / "test.json"
        data = {
            "segments": [
                {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
                {"speaker": "SPEAKER_01", "text": "World", "start": 1.0, "end": 2.0},
            ]
        }
        test_file.write_text(json.dumps(data))

        segments = load_segments(str(test_file))

        assert len(segments) == 2
        assert segments[0]["speaker"] == "SPEAKER_00"
        assert segments[1]["speaker"] == "SPEAKER_01"

    def test_loads_segments_from_list(self, tmp_path):
        """Test loading segments from direct list."""
        test_file = tmp_path / "test.json"
        data = [
            {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
            {"speaker": "SPEAKER_01", "text": "World", "start": 1.0, "end": 2.0},
        ]
        test_file.write_text(json.dumps(data))

        segments = load_segments(str(test_file))

        assert len(segments) == 2
        assert segments == data

    def test_handles_whisperx_format_with_words(self, tmp_path):
        """Test handling WhisperX format with words array."""
        test_file = tmp_path / "test.json"
        data = {
            "segments": [
                {
                    "text": "Hello world",
                    "start": 0.0,
                    "end": 2.0,
                    "words": [
                        {
                            "word": "Hello",
                            "speaker": "SPEAKER_00",
                            "start": 0.0,
                            "end": 1.0,
                        },
                        {
                            "word": "world",
                            "speaker": "SPEAKER_00",
                            "start": 1.0,
                            "end": 2.0,
                        },
                    ],
                }
            ]
        }
        test_file.write_text(json.dumps(data))

        segments = load_segments(str(test_file))

        assert len(segments) == 1
        assert segments[0]["speaker"] == "SPEAKER_00"
        assert segments[0]["text"] == "Hello world"

    def test_handles_whisperx_mixed_speakers(self, tmp_path):
        """Test handling WhisperX format with mixed speakers in words."""
        test_file = tmp_path / "test.json"
        data = {
            "segments": [
                {
                    "text": "Hello world",
                    "start": 0.0,
                    "end": 2.0,
                    "words": [
                        {
                            "word": "Hello",
                            "speaker": "SPEAKER_00",
                            "start": 0.0,
                            "end": 1.0,
                        },
                        {
                            "word": "world",
                            "speaker": "SPEAKER_01",
                            "start": 1.0,
                            "end": 2.0,
                        },
                    ],
                }
            ]
        }
        test_file.write_text(json.dumps(data))

        segments = load_segments(str(test_file))

        assert len(segments) == 1
        # Should use most common speaker (SPEAKER_00 in this case)
        assert segments[0]["speaker"] in ["SPEAKER_00", "SPEAKER_01"]

    def test_handles_whisperx_no_speaker_in_words(self, tmp_path):
        """Test handling WhisperX format with no speaker in words."""
        test_file = tmp_path / "test.json"
        data = {
            "segments": [
                {
                    "text": "Hello world",
                    "start": 0.0,
                    "end": 2.0,
                    "words": [
                        {"word": "Hello", "start": 0.0, "end": 1.0},
                        {"word": "world", "start": 1.0, "end": 2.0},
                    ],
                }
            ]
        }
        test_file.write_text(json.dumps(data))

        segments = load_segments(str(test_file))

        assert len(segments) == 1
        assert segments[0]["speaker"] == "UNKNOWN_SPEAKER"

    def test_handles_whisperx_empty_words(self, tmp_path):
        """Test handling WhisperX format with empty words array."""
        test_file = tmp_path / "test.json"
        data = {
            "segments": [{"text": "Hello world", "start": 0.0, "end": 2.0, "words": []}]
        }
        test_file.write_text(json.dumps(data))

        segments = load_segments(str(test_file))

        assert len(segments) == 1
        assert segments[0]["speaker"] == "UNKNOWN_SPEAKER"

    def test_handles_empty_segments(self, tmp_path):
        """Test handling empty segments list."""
        test_file = tmp_path / "test.json"
        data = {"segments": []}
        test_file.write_text(json.dumps(data))

        segments = load_segments(str(test_file))

        assert segments == []

    def test_handles_missing_segments_key(self, tmp_path):
        """Test handling dict without 'segments' key."""
        test_file = tmp_path / "test.json"
        data = {"metadata": {"version": "1.0"}}
        test_file.write_text(json.dumps(data))

        segments = load_segments(str(test_file))

        assert segments == []

    def test_raises_error_on_nonexistent_file(self):
        """Test that FileNotFoundError is raised for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            load_segments("/nonexistent/file.json")

    def test_handles_invalid_json(self, tmp_path):
        """Test handling invalid JSON."""
        test_file = tmp_path / "test.json"
        test_file.write_text("invalid json content")

        with pytest.raises(json.JSONDecodeError):
            load_segments(str(test_file))

    def test_load_segments_with_data_avoids_file_read(self, tmp_path):
        """When data= is provided, segments are derived from it; result matches load_segments(path)."""
        test_file = tmp_path / "test.json"
        data = {
            "segments": [
                {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
                {"speaker": "SPEAKER_01", "text": "World", "start": 1.0, "end": 2.0},
            ],
            "speaker_map": {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"},
        }
        test_file.write_text(json.dumps(data))

        from_file = load_segments(str(test_file))
        from_data = load_segments(str(test_file), data=data)

        assert from_data == from_file
        assert len(from_data) == 2
        assert from_data[0]["speaker"] == "SPEAKER_00"
        assert from_data[1]["speaker"] == "SPEAKER_01"

    def test_load_segments_with_data_whisperx_same_as_file(self, tmp_path):
        """load_segments(path, data=dict) with WhisperX format matches load_segments(path)."""
        test_file = tmp_path / "test.json"
        data = {
            "segments": [
                {
                    "text": "Hello world",
                    "start": 0.0,
                    "end": 2.0,
                    "words": [
                        {
                            "word": "Hello",
                            "speaker": "SPEAKER_00",
                            "start": 0.0,
                            "end": 1.0,
                        },
                        {
                            "word": "world",
                            "speaker": "SPEAKER_00",
                            "start": 1.0,
                            "end": 2.0,
                        },
                    ],
                }
            ]
        }
        test_file.write_text(json.dumps(data))

        from_file = load_segments(str(test_file))
        from_data = load_segments(str(test_file), data=data)

        assert from_data == from_file
        assert len(from_data) == 1
        assert from_data[0]["speaker"] == "SPEAKER_00"


class TestExtractSpeakerMapFromTranscript:
    """Tests for extract_speaker_map_from_transcript function."""

    def test_returns_metadata_speaker_map(self, tmp_path):
        transcript_path = tmp_path / "test.json"
        transcript_path.write_text(
            json.dumps(
                {
                    "segments": [{"speaker": "SPEAKER_00", "text": "Hello"}],
                    "speaker_map": {"SPEAKER_00": "Alice"},
                }
            )
        )

        result = extract_speaker_map_from_transcript(str(transcript_path))

        assert result == {"SPEAKER_00": "Alice"}

    def test_returns_empty_dict_when_missing(self, tmp_path):
        transcript_path = tmp_path / "test.json"
        transcript_path.write_text(json.dumps({"segments": []}))

        result = extract_speaker_map_from_transcript(str(transcript_path))

        assert result == {}


class TestLoadTranscript:
    """Tests for load_transcript function."""

    def test_loads_complete_transcript(self, tmp_path):
        """Test loading complete transcript file."""
        test_file = tmp_path / "test.json"
        data = {
            "segments": [{"speaker": "SPEAKER_00", "text": "Hello"}],
            "metadata": {"version": "1.0", "source": "test"},
        }
        test_file.write_text(json.dumps(data))

        loaded = load_transcript(str(test_file))

        assert loaded == data
        assert "segments" in loaded
        assert "metadata" in loaded

    def test_preserves_all_fields(self, tmp_path):
        """Test that all fields are preserved."""
        test_file = tmp_path / "test.json"
        data = {
            "segments": [{"speaker": "SPEAKER_00", "text": "Hello"}],
            "custom_field": "custom_value",
            "nested": {"key": "value"},
        }
        test_file.write_text(json.dumps(data))

        loaded = load_transcript(str(test_file))

        assert loaded == data
        assert loaded["custom_field"] == "custom_value"
        assert loaded["nested"]["key"] == "value"

    def test_raises_error_on_nonexistent_file(self):
        """Test that FileNotFoundError is raised for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            load_transcript("/nonexistent/file.json")

    def test_handles_invalid_json(self, tmp_path):
        """Test handling invalid JSON."""
        test_file = tmp_path / "test.json"
        test_file.write_text("invalid json content")

        with pytest.raises(json.JSONDecodeError):
            load_transcript(str(test_file))


class TestLoadTranscriptData:
    """Tests for load_transcript_data function."""

    def test_loads_complete_data(self, tmp_path):
        """Test loading complete transcript data."""
        test_file = tmp_path / "test.json"
        data = {
            "segments": [
                {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
            ]
        }
        test_file.write_text(json.dumps(data))

        with patch(
            "transcriptx.io.transcript_service.get_transcript_service"
        ) as mock_service:
            mock_service_instance = mock_service.return_value
            mock_service_instance.load_transcript_data.return_value = (
                data["segments"],
                "test",
                str(tmp_path),
                {"SPEAKER_00": "Alice"},
            )

            segments, base_name, transcript_dir, speaker_map = load_transcript_data(
                str(test_file)
            )

            assert len(segments) == 1
            assert base_name == "test"
            assert transcript_dir == str(tmp_path)
            assert speaker_map == {"SPEAKER_00": "Alice"}

    def test_raises_error_on_nonexistent_file(self):
        """Test that FileNotFoundError is raised for nonexistent file."""
        with patch(
            "transcriptx.io.transcript_service.get_transcript_service"
        ) as mock_service:
            mock_service_instance = mock_service.return_value
            mock_service_instance.load_transcript_data.side_effect = FileNotFoundError(
                "Transcript file not found"
            )

            with pytest.raises(FileNotFoundError):
                load_transcript_data("/nonexistent/file.json")

    def test_raises_error_on_empty_segments(self, tmp_path):
        """Test that ValueError is raised for empty segments."""
        test_file = tmp_path / "test.json"
        data = {"segments": []}
        test_file.write_text(json.dumps(data))

        with patch(
            "transcriptx.io.transcript_service.get_transcript_service"
        ) as mock_service:
            mock_service_instance = mock_service.return_value
            mock_service_instance.load_transcript_data.side_effect = ValueError(
                "No segments found"
            )

            with pytest.raises(ValueError):
                load_transcript_data(str(test_file))

    def test_passes_skip_speaker_mapping_flag(self, tmp_path):
        """Test that skip_speaker_mapping flag is passed through."""
        test_file = tmp_path / "test.json"
        data = {"segments": [{"speaker": "SPEAKER_00", "text": "Hello"}]}
        test_file.write_text(json.dumps(data))

        with patch(
            "transcriptx.io.transcript_service.get_transcript_service"
        ) as mock_service:
            mock_service_instance = mock_service.return_value
            mock_service_instance.load_transcript_data.return_value = (
                data["segments"],
                "test",
                str(tmp_path),
                {},
            )

            load_transcript_data(str(test_file), skip_speaker_mapping=True)

            mock_service_instance.load_transcript_data.assert_called_once()
            call_args = mock_service_instance.load_transcript_data.call_args
            assert call_args.kwargs.get("skip_speaker_mapping") is True

    def test_passes_batch_mode_flag(self, tmp_path):
        """Test that batch_mode flag is passed through."""
        test_file = tmp_path / "test.json"
        data = {"segments": [{"speaker": "SPEAKER_00", "text": "Hello"}]}
        test_file.write_text(json.dumps(data))

        with patch(
            "transcriptx.io.transcript_service.get_transcript_service"
        ) as mock_service:
            mock_service_instance = mock_service.return_value
            mock_service_instance.load_transcript_data.return_value = (
                data["segments"],
                "test",
                str(tmp_path),
                {},
            )

            load_transcript_data(str(test_file), batch_mode=True)

            call_args = mock_service_instance.load_transcript_data.call_args
            assert call_args.kwargs.get("batch_mode") is True
