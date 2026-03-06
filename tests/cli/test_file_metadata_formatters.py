"""
Tests for file metadata formatting functions.

This module tests formatting of audio files, transcript files, and generic files.
"""

import json
from unittest.mock import patch


from transcriptx.cli.file_metadata_formatters import (
    format_audio_file,
    format_transcript_file,
    format_readable_transcript_file,
    format_generic_file,
    is_audio_file,
)


class TestFormatAudioFile:
    """Tests for format_audio_file function."""

    def test_formats_audio_file_with_duration(self, tmp_path):
        """Test formatting audio file with duration."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio content" * 1000)  # Make it have size

        with patch(
            "transcriptx.cli.file_metadata_formatters.get_audio_duration"
        ) as mock_duration:
            mock_duration.return_value = 125.5  # 2 minutes 5 seconds

            result = format_audio_file(audio_file)

            assert "test.mp3" in result
            assert "MB" in result
            assert "2:05" in result or "2:5" in result

    def test_formats_audio_file_without_duration(self, tmp_path):
        """Test formatting audio file without duration."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio content" * 1000)

        with patch(
            "transcriptx.cli.file_metadata_formatters.get_audio_duration"
        ) as mock_duration:
            mock_duration.return_value = None

            result = format_audio_file(audio_file)

            assert "test.mp3" in result
            assert "MB" in result
            assert ":" not in result  # No duration format

    def test_handles_errors_gracefully(self, tmp_path):
        """Test that errors are handled gracefully."""
        audio_file = tmp_path / "test.mp3"

        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.side_effect = OSError("Permission denied")

            result = format_audio_file(audio_file)

            # Should return basic format
            assert "test.mp3" in result


class TestFormatTranscriptFile:
    """Tests for format_transcript_file function."""

    def test_formats_transcript_with_segments(self, tmp_path):
        """Test formatting transcript file with segments."""
        transcript_file = tmp_path / "test.json"
        data = {
            "segments": [
                {"speaker": "SPEAKER_00", "text": "Hello"},
                {"speaker": "SPEAKER_01", "text": "World"},
            ]
        }
        transcript_file.write_text(json.dumps(data))

        result = format_transcript_file(transcript_file)

        assert "test.json" in result
        assert "KB" in result
        assert "2 segments" in result or "segments" in result

    def test_formats_transcript_with_text(self, tmp_path):
        """Test formatting transcript file with text field."""
        transcript_file = tmp_path / "test.json"
        data = {"text": "Hello world " * 10}
        transcript_file.write_text(json.dumps(data))

        result = format_transcript_file(transcript_file)

        assert "test.json" in result
        assert "KB" in result
        assert "chars" in result

    def test_formats_transcript_without_metadata(self, tmp_path):
        """Test formatting transcript file without readable metadata."""
        transcript_file = tmp_path / "test.json"
        transcript_file.write_text("{}")

        result = format_transcript_file(transcript_file)

        assert "test.json" in result
        assert "KB" in result

    def test_handles_errors_gracefully(self, tmp_path):
        """Test that errors are handled gracefully."""
        transcript_file = tmp_path / "test.json"

        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.side_effect = OSError("Permission denied")

            result = format_transcript_file(transcript_file)

            # Should return basic format
            assert "test.json" in result


class TestFormatReadableTranscriptFile:
    """Tests for format_readable_transcript_file function."""

    def test_formats_csv_file(self, tmp_path):
        """Test formatting CSV transcript file."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("Speaker,Text\nAlice,Hello")

        result = format_readable_transcript_file(csv_file)

        assert "test.csv" in result
        assert "KB" in result
        assert "CSV" in result

    def test_formats_txt_file(self, tmp_path):
        """Test formatting TXT transcript file."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Hello world")

        result = format_readable_transcript_file(txt_file)

        assert "test.txt" in result
        assert "KB" in result
        assert "TXT" in result

    def test_handles_errors_gracefully(self, tmp_path):
        """Test that errors are handled gracefully."""
        txt_file = tmp_path / "test.txt"

        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.side_effect = OSError("Permission denied")

            result = format_readable_transcript_file(txt_file)

            # Should return basic format
            assert "test.txt" in result


class TestFormatGenericFile:
    """Tests for format_generic_file function."""

    def test_formats_generic_file(self, tmp_path):
        """Test formatting generic file."""
        generic_file = tmp_path / "test.unknown"
        generic_file.write_text("some content")

        result = format_generic_file(generic_file)

        assert "test.unknown" in result
        assert "KB" in result

    def test_handles_errors_gracefully(self, tmp_path):
        """Test that errors are handled gracefully."""
        generic_file = tmp_path / "test.unknown"

        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.side_effect = OSError("Permission denied")

            result = format_generic_file(generic_file)

            # Should return basic format
            assert "test.unknown" in result


class TestIsAudioFile:
    """Tests for is_audio_file function."""

    def test_identifies_audio_files(self, tmp_path):
        """Test that audio files are identified correctly."""
        audio_extensions = [".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"]

        for ext in audio_extensions:
            audio_file = tmp_path / f"test{ext}"
            audio_file.touch()

            assert is_audio_file(audio_file) is True

    def test_rejects_non_audio_files(self, tmp_path):
        """Test that non-audio files are rejected."""
        non_audio_file = tmp_path / "test.txt"
        non_audio_file.touch()

        assert is_audio_file(non_audio_file) is False

    def test_handles_files_without_extension(self, tmp_path):
        """Test that files without extension are handled."""
        no_ext_file = tmp_path / "test"
        no_ext_file.touch()

        assert is_audio_file(no_ext_file) is False
