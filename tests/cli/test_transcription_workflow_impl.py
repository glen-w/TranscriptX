"""
Tests for transcription workflow implementation.

This module tests the _run_transcription_workflow_impl() function including
WhisperX integration, audio selection, service management, and post-transcription analysis.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.quarantined, pytest.mark.xfail(strict=True, reason="quarantined")]  # reason: patches select_audio_file/validate_transcript_file/start_whisperx_compose_service; API uses target not transcript_path; owner: cli; remove_by: when transcription_workflow API stabilizes

from transcriptx.cli.transcription_workflow import (
    _run_transcription_workflow_impl,
    _run_post_transcription_analysis
)


class TestTranscriptionWorkflowImpl:
    """Tests for _run_transcription_workflow_impl function."""
    
    @patch('transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription')
    @patch('transcriptx.cli.transcription_workflow.transcribe_with_whisperx')
    @patch('transcriptx.cli.transcription_workflow.questionary.confirm')
    @patch('transcriptx.cli.transcription_workflow._run_post_transcription_analysis')
    def test_transcription_workflow_complete_flow(
        self, mock_post_analysis, mock_confirm, mock_transcribe,
        mock_select_audio, tmp_path, mock_config
    ):
        """Test complete transcription workflow."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        transcript_path = str(tmp_path / "transcript.json")
        
        mock_select_audio.return_value = audio_file
        mock_transcribe.return_value = transcript_path
        mock_confirm.return_value.ask.return_value = True  # User wants analysis
        
        _run_transcription_workflow_impl()
        
        mock_select_audio.assert_called_once()
        mock_transcribe.assert_called_once()
        mock_confirm.assert_called_once()
        mock_post_analysis.assert_called_once_with(transcript_path)
    
    @patch('transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription')
    def test_transcription_workflow_no_audio_selected(self, mock_select_audio):
        """Test workflow when no audio file is selected."""
        mock_select_audio.return_value = None
        
        _run_transcription_workflow_impl()
        
        # Should return early
        mock_select_audio.assert_called_once()
    
    @patch('transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription')
    @patch('transcriptx.cli.transcription_workflow.transcribe_with_whisperx')
    @patch('transcriptx.cli.transcription_workflow.questionary.confirm')
    def test_transcription_workflow_no_analysis(
        self, mock_confirm, mock_transcribe, mock_select_audio,
        tmp_path, mock_config
    ):
        """Test workflow when user declines analysis."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        transcript_path = str(tmp_path / "transcript.json")
        
        mock_select_audio.return_value = audio_file
        mock_transcribe.return_value = transcript_path
        mock_confirm.return_value.ask.return_value = False  # User declines
        
        _run_transcription_workflow_impl()
        
        mock_transcribe.assert_called_once()
        mock_confirm.assert_called_once()
    
    @patch('transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription')
    @patch('transcriptx.cli.transcription_workflow.transcribe_with_whisperx')
    def test_transcription_workflow_transcription_fails(
        self, mock_transcribe, mock_select_audio, tmp_path, mock_config
    ):
        """Test workflow when transcription fails."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        
        mock_select_audio.return_value = audio_file
        mock_transcribe.return_value = None  # Transcription failed
        
        with patch('transcriptx.cli.transcription_workflow.log_error') as mock_log:
            _run_transcription_workflow_impl()
        
        mock_transcribe.assert_called_once()
        mock_log.assert_called_once()


class TestPostTranscriptionAnalysis:
    """Tests for _run_post_transcription_analysis function."""
    
    @patch('transcriptx.cli.transcription_workflow.select_analysis_mode')
    @patch('transcriptx.cli.transcription_workflow.apply_analysis_mode_settings')
    @patch('transcriptx.cli.transcription_workflow.get_available_modules')
    @patch('transcriptx.cli.transcription_workflow.questionary.confirm')
    @patch('transcriptx.cli.transcription_workflow.run_analysis_pipeline')
    def test_post_transcription_analysis_complete(
        self, mock_pipeline, mock_confirm, mock_get_modules,
        mock_apply_settings, mock_select_mode, temp_transcript_file
    ):
        """Test complete post-transcription analysis."""
        mock_select_mode.return_value = "full"
        mock_get_modules.return_value = ["sentiment", "stats", "ner"]
        mock_confirm.return_value.ask.return_value = True
        mock_pipeline.return_value = {
            "modules_run": ["sentiment", "stats", "ner"],
            "errors": []
        }
        
        _run_post_transcription_analysis(str(temp_transcript_file))
        
        mock_select_mode.assert_called_once()
        mock_apply_settings.assert_called_once_with("full")
        mock_confirm.assert_called_once()
        mock_pipeline.assert_called_once_with(
            transcript_path=str(temp_transcript_file),
            selected_modules=["sentiment", "stats", "ner"],
            skip_speaker_mapping=True
        )
    
    @patch('transcriptx.cli.transcription_workflow.select_analysis_mode')
    @patch('transcriptx.cli.transcription_workflow.apply_analysis_mode_settings')
    @patch('transcriptx.cli.transcription_workflow.get_available_modules')
    @patch('transcriptx.cli.transcription_workflow.questionary.confirm')
    def test_post_transcription_analysis_user_cancels(
        self, mock_confirm, mock_get_modules,
        mock_apply_settings, mock_select_mode, temp_transcript_file
    ):
        """Test when user cancels post-transcription analysis."""
        mock_select_mode.return_value = "quick"
        mock_get_modules.return_value = ["sentiment"]
        mock_confirm.return_value.ask.return_value = False  # User cancels
        
        _run_post_transcription_analysis(str(temp_transcript_file))
        
        # Should not run pipeline
        mock_confirm.assert_called_once()
    
    @patch('transcriptx.cli.transcription_workflow.select_analysis_mode')
    @patch('transcriptx.cli.transcription_workflow.apply_analysis_mode_settings')
    @patch('transcriptx.cli.transcription_workflow.get_available_modules')
    @patch('transcriptx.cli.transcription_workflow.questionary.confirm')
    @patch('transcriptx.cli.transcription_workflow.run_analysis_pipeline')
    def test_post_transcription_analysis_pipeline_error(
        self, mock_pipeline, mock_confirm, mock_get_modules,
        mock_apply_settings, mock_select_mode, temp_transcript_file
    ):
        """Test when analysis pipeline raises error."""
        mock_select_mode.return_value = "full"
        mock_get_modules.return_value = ["sentiment"]
        mock_confirm.return_value.ask.return_value = True
        mock_pipeline.side_effect = Exception("Pipeline error")
        
        with patch('transcriptx.cli.transcription_workflow.log_error') as mock_log:
            _run_post_transcription_analysis(str(temp_transcript_file))
        
        mock_pipeline.assert_called_once()
        mock_log.assert_called_once()


class TestTranscriptionWorkflowErrorHandling:
    """Tests for error handling in transcription workflow."""
    
    @patch('transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription')
    @patch('transcriptx.cli.transcription_workflow.check_whisperx_compose_service')
    @patch('transcriptx.cli.transcription_workflow.start_whisperx_compose_service')
    def test_whisperx_service_startup_failure(
        self, mock_start, mock_check, mock_select_audio, tmp_path
    ):
        """Test handling when WhisperX service fails to start."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        
        mock_select_audio.return_value = audio_file
        mock_check.return_value = False
        mock_start.return_value = False  # Startup failed
        
        with patch('transcriptx.cli.transcription_workflow.transcribe_with_whisperx') as mock_transcribe, \
             patch('transcriptx.cli.transcription_workflow.log_error') as mock_log_error:
            
            mock_transcribe.return_value = None
            
            _run_transcription_workflow_impl()
        
        # Should handle startup failure
        mock_start.assert_called()
        mock_log_error.assert_called()
    
    @patch('transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription')
    @patch('transcriptx.cli.transcription_workflow.transcribe_with_whisperx')
    def test_whisperx_service_crash_during_transcription(
        self, mock_transcribe, mock_select_audio, tmp_path
    ):
        """Test handling when WhisperX service crashes during transcription."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        
        mock_select_audio.return_value = audio_file
        mock_transcribe.side_effect = Exception("Service crashed")
        
        with patch('transcriptx.cli.transcription_workflow.log_error') as mock_log_error:
            _run_transcription_workflow_impl()
        
        # Should handle crash gracefully
        mock_log_error.assert_called()
    
    @patch('transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription')
    @patch('transcriptx.cli.transcription_workflow.transcribe_with_whisperx')
    def test_whisperx_service_timeout(
        self, mock_transcribe, mock_select_audio, tmp_path
    ):
        """Test handling when WhisperX service times out."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        
        mock_select_audio.return_value = audio_file
        mock_transcribe.side_effect = TimeoutError("Service timeout")
        
        with patch('transcriptx.cli.transcription_workflow.log_error') as mock_log_error:
            _run_transcription_workflow_impl()
        
        # Should handle timeout
        mock_log_error.assert_called()
    
    @patch('transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription')
    def test_corrupted_audio_file(self, mock_select_audio, tmp_path):
        """Test handling of corrupted audio file."""
        corrupted_file = tmp_path / "corrupted.mp3"
        corrupted_file.write_bytes(b"not really audio")
        
        mock_select_audio.return_value = corrupted_file
        
        with patch('transcriptx.cli.transcription_workflow.transcribe_with_whisperx') as mock_transcribe, \
             patch('transcriptx.cli.transcription_workflow.log_error') as mock_log_error:
            
            mock_transcribe.return_value = None  # Transcription fails
            
            _run_transcription_workflow_impl()
        
        # Should detect and handle corrupted file
        mock_transcribe.assert_called_once()
    
    @patch('transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription')
    def test_unsupported_audio_format(self, mock_select_audio, tmp_path):
        """Test handling of unsupported audio format."""
        unsupported_file = tmp_path / "test.xyz"
        unsupported_file.write_bytes(b"unknown format")
        
        mock_select_audio.return_value = unsupported_file
        
        with patch('transcriptx.cli.transcription_workflow.transcribe_with_whisperx') as mock_transcribe, \
             patch('transcriptx.cli.transcription_workflow.log_error') as mock_log_error:
            
            mock_transcribe.return_value = None
            
            _run_transcription_workflow_impl()
        
        # Should handle unsupported format
        mock_transcribe.assert_called_once()
    
    @patch('transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription')
    def test_audio_file_too_large(self, mock_select_audio, tmp_path):
        """Test handling when audio file is too large."""
        # Create a large file (simulate)
        large_file = tmp_path / "large.mp3"
        large_file.write_bytes(b"x" * 1000000)  # 1MB
        
        mock_select_audio.return_value = large_file
        
        with patch('transcriptx.cli.transcription_workflow.transcribe_with_whisperx') as mock_transcribe:
            # Simulate file size check failure
            mock_transcribe.return_value = None
            
            _run_transcription_workflow_impl()
        
        # Should handle large file (may need conversion or error)
        mock_transcribe.assert_called_once()
    
    @patch('transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription')
    @patch('transcriptx.cli.transcription_workflow.transcribe_with_whisperx')
    def test_transcription_timeout(
        self, mock_transcribe, mock_select_audio, tmp_path
    ):
        """Test handling when transcription times out."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        
        mock_select_audio.return_value = audio_file
        mock_transcribe.side_effect = TimeoutError("Transcription timeout")
        
        with patch('transcriptx.cli.transcription_workflow.log_error') as mock_log_error:
            _run_transcription_workflow_impl()
        
        # Should handle timeout
        mock_log_error.assert_called()
    
    @patch('transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription')
    @patch('transcriptx.cli.transcription_workflow.transcribe_with_whisperx')
    def test_transcription_returns_empty(
        self, mock_transcribe, mock_select_audio, tmp_path
    ):
        """Test handling when transcription returns empty result."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        
        mock_select_audio.return_value = audio_file
        mock_transcribe.return_value = None  # Empty result
        
        with patch('transcriptx.cli.transcription_workflow.log_error') as mock_log_error:
            _run_transcription_workflow_impl()
        
        # Should handle empty result
        mock_log_error.assert_called()
    
    @patch('transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription')
    @patch('transcriptx.cli.transcription_workflow.transcribe_with_whisperx')
    def test_transcription_returns_malformed_data(
        self, mock_transcribe, mock_select_audio, tmp_path
    ):
        """Test handling when transcription returns malformed data."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        
        mock_select_audio.return_value = audio_file
        # Return path to non-existent or invalid file
        mock_transcribe.return_value = str(tmp_path / "invalid.json")
        
        with patch('transcriptx.cli.transcription_workflow.validate_transcript_file') as mock_validate, \
             patch('transcriptx.cli.transcription_workflow.log_error') as mock_log_error:
            
            mock_validate.side_effect = ValueError("Invalid transcript structure")
            
            # Should handle validation error if checked
            _run_transcription_workflow_impl()
        
        # Transcription completed but data invalid
        mock_transcribe.assert_called_once()
    
    @patch('transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription')
    @patch('transcriptx.cli.transcription_workflow.transcribe_with_whisperx')
    def test_output_directory_not_writable(
        self, mock_transcribe, mock_select_audio, tmp_path
    ):
        """Test handling when output directory is not writable."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        
        mock_select_audio.return_value = audio_file
        mock_transcribe.side_effect = PermissionError("Permission denied")
        
        with patch('transcriptx.cli.transcription_workflow.log_error') as mock_log_error:
            _run_transcription_workflow_impl()
        
        # Should handle permission error
        mock_log_error.assert_called()
    
    @patch('transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription')
    @patch('transcriptx.cli.transcription_workflow.transcribe_with_whisperx')
    def test_disk_space_insufficient(
        self, mock_transcribe, mock_select_audio, tmp_path
    ):
        """Test handling when disk space is insufficient."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        
        mock_select_audio.return_value = audio_file
        mock_transcribe.side_effect = OSError("No space left on device")
        
        with patch('transcriptx.cli.transcription_workflow.log_error') as mock_log_error:
            _run_transcription_workflow_impl()
        
        # Should handle disk space error
        mock_log_error.assert_called()
    
    @patch('transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription')
    @patch('transcriptx.cli.transcription_workflow.transcribe_with_whisperx')
    def test_file_lock_conflict(
        self, mock_transcribe, mock_select_audio, tmp_path
    ):
        """Test handling when file is locked."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        
        mock_select_audio.return_value = audio_file
        mock_transcribe.side_effect = BlockingIOError("Resource temporarily unavailable")
        
        with patch('transcriptx.cli.transcription_workflow.log_error') as mock_log_error:
            _run_transcription_workflow_impl()
        
        # Should handle file lock error
        mock_log_error.assert_called()
