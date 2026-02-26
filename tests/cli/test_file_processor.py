"""
Tests for file processing utilities.

This module tests file processing, renaming, and metadata operations.
"""

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.cli.file_processor import process_single_file


class TestProcessSingleFile:
    """Tests for process_single_file function."""

    @pytest.mark.quarantined
    @pytest.mark.xfail(strict=True, reason="success path needs more isolation (paths/state/DB)")
    @patch("transcriptx.cli.file_processor._get_tracking_service")
    @patch("transcriptx.cli.file_processor._store_metadata_in_database")
    @patch("transcriptx.cli.file_processor.mark_file_processed")
    @patch("transcriptx.cli.file_processor.convert_audio_to_mp3")
    @patch("transcriptx.cli.file_processor.transcribe_with_whisperx")
    @patch("transcriptx.core.analysis.conversation_type.detect_conversation_type")
    @patch("transcriptx.core.analysis.tag_extraction.extract_tags")
    @patch("transcriptx.cli.file_processor.compute_audio_fingerprint", return_value=None)
    def test_process_single_file_success(
        self,
        mock_fingerprint,
        mock_extract_tags,
        mock_detect_type,
        mock_transcribe,
        mock_convert,
        mock_mark_processed,
        mock_store_meta,
        mock_tracking,
        tmp_path,
    ):
        """Test successful file processing."""
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake wav")
        mp3_file = tmp_path / "test.mp3"
        transcript_file = tmp_path / "transcript.json"
        transcript_file.write_text('{"segments": []}')

        mock_convert.return_value = mp3_file
        mock_transcribe.return_value = str(transcript_file)
        mock_detect_type.return_value = {"type": "conversation", "confidence": 0.9}
        mock_extract_tags.return_value = {"tags": ["tag1"], "tag_details": {}}
        mock_tracking.return_value = (MagicMock(), MagicMock())

        with (
            patch("transcriptx.cli.file_processor.RECORDINGS_DIR", str(tmp_path)),
            patch("transcriptx.cli.file_processor.DIARISED_TRANSCRIPTS_DIR", str(tmp_path)),
        ):
            result = process_single_file(wav_file)

        assert result["file"] == str(wav_file)
        assert "steps" in result
        mock_convert.assert_called_once()
        assert result["status"] == "success"

    @patch("transcriptx.cli.file_processor.mark_file_processed")
    @patch("transcriptx.cli.file_processor.convert_audio_to_mp3")
    @patch("transcriptx.cli.file_processor.compute_audio_fingerprint", return_value=None)
    def test_process_single_file_conversion_fails(
        self, mock_fingerprint, mock_convert, mock_mark, tmp_path
    ):
        """Test when conversion fails."""
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake wav")

        mock_convert.side_effect = Exception("Conversion error")

        with patch("transcriptx.cli.file_processor.RECORDINGS_DIR", str(tmp_path)):
            result = process_single_file(wav_file)

        assert result["status"] in ("failed", "error")
        assert "error" in result

    @patch("transcriptx.cli.file_processor.mark_file_processed")
    @patch("transcriptx.cli.file_processor.convert_audio_to_mp3")
    @patch("transcriptx.cli.file_processor.transcribe_with_whisperx")
    @patch("transcriptx.cli.file_processor.compute_audio_fingerprint", return_value=None)
    def test_process_single_file_transcription_fails(
        self, mock_fingerprint, mock_transcribe, mock_convert, mock_mark, tmp_path
    ):
        """Test when transcription fails."""
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake wav")
        mp3_file = tmp_path / "test.mp3"

        mock_convert.return_value = mp3_file
        mock_transcribe.side_effect = Exception("Transcription failed")

        with (
            patch("transcriptx.cli.file_processor.RECORDINGS_DIR", str(tmp_path)),
            patch("transcriptx.cli.file_processor.DIARISED_TRANSCRIPTS_DIR", str(tmp_path)),
        ):
            result = process_single_file(wav_file)

        assert result["status"] in ("failed", "error")
        assert "error" in result
