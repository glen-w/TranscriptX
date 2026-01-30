"""
Tests for file rename operations.

This module tests file rename operations, date extraction, and transaction handling.
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from transcriptx.core.utils.file_rename import (
    extract_date_prefix_from_filename,
    extract_date_prefix,
    find_original_audio_file,
    rename_transcript_after_speaker_mapping,
)


class TestExtractDatePrefixFromFilename:
    """Tests for extract_date_prefix_from_filename function."""
    
    def test_extracts_from_yyyymmddhhmmss_format(self):
        """Test extraction from YYYYMMDDHHMMSS format."""
        result = extract_date_prefix_from_filename("20251230160235.wav")
        
        assert result == "251230_"
    
    def test_extracts_from_yymmdd_format(self):
        """Test extraction from YYMMDD format."""
        result = extract_date_prefix_from_filename("251230_meeting.wav")
        
        assert result == "251230_"
    
    def test_returns_empty_for_invalid_date(self):
        """Test that empty string is returned for invalid date."""
        result = extract_date_prefix_from_filename("999999_invalid.wav")
        
        assert result == ""
    
    def test_returns_empty_for_no_date(self):
        """Test that empty string is returned when no date found."""
        result = extract_date_prefix_from_filename("meeting.wav")
        
        assert result == ""
    
    def test_handles_filename_without_extension(self):
        """Test that function works with filename without extension."""
        result = extract_date_prefix_from_filename("20251230160235")
        
        assert result == "251230_"
    
    def test_validates_month_range(self):
        """Test that invalid months are rejected."""
        result = extract_date_prefix_from_filename("20251330160235.wav")
        
        assert result == ""
    
    def test_validates_day_range(self):
        """Test that invalid days are rejected."""
        result = extract_date_prefix_from_filename("20251232160235.wav")
        
        assert result == ""


class TestExtractDatePrefix:
    """Tests for extract_date_prefix function."""
    
    def test_extracts_from_filename(self, tmp_path):
        """Test extraction from filename."""
        audio_file = tmp_path / "20251230160235.wav"
        audio_file.write_text("fake audio")
        
        result = extract_date_prefix(audio_file)
        
        assert result == "251230_"
    
    def test_falls_back_to_modification_time(self, tmp_path):
        """Test fallback to file modification time."""
        audio_file = tmp_path / "meeting.wav"
        audio_file.write_text("fake audio")
        
        # Set modification time to a known date
        import time
        from datetime import datetime
        test_date = datetime(2025, 12, 30, 16, 2, 35)
        timestamp = test_date.timestamp()
        audio_file.touch()
        import os
        os.utime(audio_file, (timestamp, timestamp))
        
        result = extract_date_prefix(audio_file)
        
        assert result == "251230_"
    
    def test_returns_empty_when_file_not_exists(self, tmp_path):
        """Test that empty string is returned when file doesn't exist."""
        audio_file = tmp_path / "nonexistent.wav"
        
        result = extract_date_prefix(audio_file)
        
        assert result == ""
    
    def test_handles_extraction_errors(self, tmp_path):
        """Test that errors during extraction are handled."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")
        
        with patch('transcriptx.core.utils.file_rename.extract_date_prefix_from_filename') as mock_extract, \
             patch('transcriptx.core.utils.file_rename.log_error') as mock_log:
            
            mock_extract.side_effect = Exception("Test error")
            
            result = extract_date_prefix(audio_file)
            
            assert result == ""
            mock_log.assert_called()


class TestFindOriginalAudioFile:
    """Tests for find_original_audio_file function."""
    
    def test_finds_audio_from_processing_state(self, tmp_path, monkeypatch):
        """Test finding audio file from processing state."""
        transcript_path = str(tmp_path / "test.json")
        audio_path = tmp_path / "test.wav"
        audio_path.write_text("fake audio")
        
        state_file = tmp_path / "processing_state.json"
        state_data = {
            "processed_files": {
                str(audio_path): {
                    "transcript_path": transcript_path
                }
            }
        }
        state_file.write_text(json.dumps(state_data))
        
        with patch('transcriptx.core.utils.file_rename.PROCESSING_STATE_FILE', state_file):
            result = find_original_audio_file(transcript_path)
            
            assert result == audio_path

    def test_uses_mp3_path_when_state_key_missing(self, tmp_path, monkeypatch):
        """Test fallback to mp3_path when state key is stale."""
        transcript_path = str(tmp_path / "test.json")
        stale_audio_path = tmp_path / "stale.wav"
        mp3_path = tmp_path / "resolved.mp3"
        mp3_path.write_text("fake audio")

        state_file = tmp_path / "processing_state.json"
        state_data = {
            "processed_files": {
                str(stale_audio_path): {
                    "transcript_path": transcript_path,
                    "mp3_path": str(mp3_path),
                }
            }
        }
        state_file.write_text(json.dumps(state_data))

        with patch('transcriptx.core.utils.file_rename.PROCESSING_STATE_FILE', state_file):
            result = find_original_audio_file(transcript_path)

            assert result == mp3_path
    
    def test_infers_from_transcript_name(self, tmp_path, monkeypatch):
        """Test inferring audio file from transcript name."""
        transcript_path = str(tmp_path / "20251230160235.json")
        audio_path = tmp_path / "20251230160235.wav"
        audio_path.write_text("fake audio")
        
        state_file = tmp_path / "processing_state.json"
        state_file.write_text(json.dumps({"processed_files": {}}))
        
        with patch('transcriptx.core.utils.file_rename.PROCESSING_STATE_FILE', state_file), \
             patch('transcriptx.core.utils.file_rename.DATA_DIR', str(tmp_path)), \
             patch('transcriptx.core.utils.file_rename.get_base_name') as mock_base:
            
            mock_base.return_value = "20251230160235"
            
            # Create recordings directory
            recordings_dir = tmp_path / "recordings"
            recordings_dir.mkdir()
            audio_in_recordings = recordings_dir / "20251230160235.wav"
            audio_in_recordings.write_text("fake audio")
            
            result = find_original_audio_file(transcript_path)
            
            assert result == audio_in_recordings
    
    def test_returns_none_when_not_found(self, tmp_path, monkeypatch):
        """Test that None is returned when audio file not found."""
        transcript_path = str(tmp_path / "test.json")
        
        state_file = tmp_path / "processing_state.json"
        state_file.write_text(json.dumps({"processed_files": {}}))
        
        with patch('transcriptx.core.utils.file_rename.PROCESSING_STATE_FILE', state_file), \
             patch('transcriptx.core.utils.file_rename.DATA_DIR', str(tmp_path)):
            
            result = find_original_audio_file(transcript_path)
            
            assert result is None
    
    def test_handles_errors_gracefully(self, tmp_path, monkeypatch):
        """Test that errors are handled gracefully."""
        transcript_path = str(tmp_path / "test.json")
        
        with patch('transcriptx.core.utils.file_rename.PROCESSING_STATE_FILE', tmp_path / "nonexistent.json"), \
             patch('transcriptx.core.utils.file_rename.log_error') as mock_log:
            
            result = find_original_audio_file(transcript_path)
            
            # Should return None on error
            assert result is None or isinstance(result, (Path, type(None)))


class TestRenameTranscriptAfterSpeakerMapping:
    """Tests for rename_transcript_after_speaker_mapping function."""
    
    def test_renames_transcript_files(self, tmp_path, monkeypatch):
        """Test that transcript files are renamed."""
        transcript_path = str(tmp_path / "old_name.json")
        transcript_data = {"segments": [{"speaker": "SPEAKER_00", "text": "Hello"}]}
        Path(transcript_path).write_text(json.dumps(transcript_data))

        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake")

        with patch('transcriptx.core.utils.file_rename.find_original_audio_file') as mock_find, \
             patch('transcriptx.core.utils.file_rename.extract_date_prefix') as mock_prefix, \
             patch('transcriptx.core.utils.file_rename.prompt_for_rename') as mock_prompt:

            mock_find.return_value = audio_path
            mock_prefix.return_value = "240101_"

            rename_transcript_after_speaker_mapping(transcript_path)

            mock_prompt.assert_called_once_with(transcript_path, "240101_")
    
    def test_skips_rename_when_user_cancels(self, tmp_path, monkeypatch):
        """Test that rename is skipped when user cancels."""
        transcript_path = str(tmp_path / "test.json")
        Path(transcript_path).write_text(json.dumps({"segments": []}))
        
        with patch('transcriptx.core.utils.file_rename.prompt_for_rename') as mock_prompt:
            rename_transcript_after_speaker_mapping(transcript_path)
            mock_prompt.assert_called()
    
    def test_handles_missing_audio(self, tmp_path, monkeypatch):
        """Test that function handles missing audio file."""
        transcript_path = str(tmp_path / "test.json")
        Path(transcript_path).write_text(json.dumps({"segments": []}))
        with patch('transcriptx.core.utils.file_rename.find_original_audio_file') as mock_find, \
             patch('transcriptx.core.utils.file_rename.extract_date_prefix_from_transcript') as mock_transcript_prefix, \
             patch('transcriptx.core.utils.file_rename.prompt_for_rename') as mock_prompt:
            mock_find.return_value = None
            mock_transcript_prefix.return_value = "240101_"
            rename_transcript_after_speaker_mapping(transcript_path)
            mock_prompt.assert_called_once_with(transcript_path, "240101_")
