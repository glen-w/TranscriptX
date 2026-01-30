"""
Tests for file processing utilities.

This module tests file processing, renaming, and metadata operations.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.cli.file_processor import process_single_file


class TestProcessSingleFile:
    """Tests for process_single_file function."""
    
    @patch('transcriptx.cli.file_processor.convert_wav_to_mp3')
    @patch('transcriptx.cli.file_processor.transcribe_with_whisperx')
    @patch('transcriptx.cli.file_processor.detect_conversation_type')
    @patch('transcriptx.cli.file_processor.extract_tags_from_transcript')
    def test_process_single_file_success(
        self, mock_extract_tags, mock_detect_type,
        mock_transcribe, mock_convert, tmp_path
    ):
        """Test successful file processing."""
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake wav")
        mp3_file = tmp_path / "test.mp3"
        transcript_file = tmp_path / "transcript.json"
        transcript_file.write_text('{"segments": []}')
        
        mock_convert.return_value = mp3_file
        mock_transcribe.return_value = str(transcript_file)
        mock_detect_type.return_value = {"type": "conversation"}
        mock_extract_tags.return_value = {"tags": ["tag1"]}
        
        result = process_single_file(wav_file)
        
        assert result["status"] == "success"
        assert result["file"] == str(wav_file)
        assert "steps" in result
        mock_convert.assert_called_once()
        mock_transcribe.assert_called_once()
    
    @patch('transcriptx.cli.file_processor.convert_wav_to_mp3')
    def test_process_single_file_conversion_fails(self, mock_convert, tmp_path):
        """Test when conversion fails."""
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake wav")
        
        mock_convert.side_effect = Exception("Conversion error")
        
        result = process_single_file(wav_file)
        
        assert result["status"] == "error"
        assert "error" in result
    
    @patch('transcriptx.cli.file_processor.convert_wav_to_mp3')
    @patch('transcriptx.cli.file_processor.transcribe_with_whisperx')
    def test_process_single_file_transcription_fails(
        self, mock_transcribe, mock_convert, tmp_path
    ):
        """Test when transcription fails."""
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake wav")
        mp3_file = tmp_path / "test.mp3"
        
        mock_convert.return_value = mp3_file
        mock_transcribe.return_value = None  # Transcription failed
        
        result = process_single_file(wav_file)
        
        assert result["status"] == "error"
        assert "error" in result
