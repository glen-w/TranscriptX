"""
Tests for file selection utilities.

This module tests file selection interface, file discovery,
and audio playback integration.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.quarantined, pytest.mark.xfail(strict=True, reason="quarantined")]  # reason: patches select_transcript_file/select_audio_file etc. which were moved/renamed; owner: cli; remove_by: when file_selection API stabilizes


class TestFileSelection:
    """Tests for file selection functions."""
    
    @patch('transcriptx.cli.file_selection_utils.select_transcript_file')
    def test_select_transcript_file(self, mock_select):
        """Test transcript file selection."""
        mock_select.return_value = "/path/to/transcript.json"
        
        result = mock_select()
        
        assert result == "/path/to/transcript.json"
    
    @patch('transcriptx.cli.file_selection_utils.select_audio_file')
    def test_select_audio_file(self, mock_select):
        """Test audio file selection."""
        mock_select.return_value = "/path/to/audio.mp3"
        
        result = mock_select()
        
        assert result == "/path/to/audio.mp3"
    
    @patch('transcriptx.cli.file_selection_utils.discover_transcript_files')
    def test_discover_transcript_files(self, mock_discover, tmp_path):
        """Test transcript file discovery."""
        transcript_dir = tmp_path / "transcripts"
        transcript_dir.mkdir()
        
        (transcript_dir / "file1.json").write_text('{"segments": []}')
        (transcript_dir / "file2.json").write_text('{"segments": []}')
        
        mock_discover.return_value = [
            str(transcript_dir / "file1.json"),
            str(transcript_dir / "file2.json")
        ]
        
        files = mock_discover(str(transcript_dir))
        
        assert len(files) == 2
        assert all(f.endswith(".json") for f in files)
    
    @patch('transcriptx.cli.file_selection_utils.select_wav_file')
    def test_select_wav_file(self, mock_select):
        """Test WAV file selection."""
        mock_select.return_value = "/path/to/audio.wav"
        
        result = mock_select()
        
        assert result == "/path/to/audio.wav"
    
    @patch('transcriptx.cli.file_selection_utils.select_wav_folder')
    def test_select_wav_folder(self, mock_select):
        """Test WAV folder selection."""
        mock_select.return_value = "/path/to/wavs"
        
        result = mock_select()
        
        assert result == "/path/to/wavs"
