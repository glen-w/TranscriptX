"""
Tests for WAV processing workflow implementation.

This module tests WAV file processing including conversion to MP3,
merging files, and file management operations.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.cli.wav_processing_workflow import (
    _run_wav_processing_workflow_impl,
    _run_convert_workflow,
    _run_merge_workflow
)


class TestWAVProcessingWorkflowImpl:
    """Tests for _run_wav_processing_workflow_impl function."""
    
    @patch('transcriptx.cli.wav_processing_workflow.check_ffmpeg_available')
    @patch('transcriptx.cli.wav_processing_workflow.questionary.select')
    def test_wav_workflow_ffmpeg_not_available(self, mock_select, mock_check_ffmpeg):
        """Test workflow when ffmpeg is not available."""
        mock_check_ffmpeg.return_value = (False, "ffmpeg not found")
        
        _run_wav_processing_workflow_impl()
        
        # Should show error and return
        mock_check_ffmpeg.assert_called_once()
    
    @patch('transcriptx.cli.wav_processing_workflow.check_ffmpeg_available')
    @patch('transcriptx.cli.wav_processing_workflow.questionary.select')
    def test_wav_workflow_convert_choice(self, mock_select, mock_check_ffmpeg):
        """Test selecting convert option."""
        mock_check_ffmpeg.return_value = (True, None)
        mock_select.return_value.ask.return_value = "🔄 Convert WAV to MP3"
        
        with patch('transcriptx.cli.wav_processing_workflow._run_convert_workflow') as mock_convert:
            _run_wav_processing_workflow_impl()
        
        mock_convert.assert_called_once()
    
    @patch('transcriptx.cli.wav_processing_workflow.check_ffmpeg_available')
    @patch('transcriptx.cli.wav_processing_workflow.questionary.select')
    def test_wav_workflow_merge_choice(self, mock_select, mock_check_ffmpeg):
        """Test selecting merge option."""
        mock_check_ffmpeg.return_value = (True, None)
        mock_select.return_value.ask.return_value = "🔗 Merge WAV Files"
        
        with patch('transcriptx.cli.wav_processing_workflow._run_merge_workflow') as mock_merge:
            _run_wav_processing_workflow_impl()
        
        mock_merge.assert_called_once()
    
    @patch('transcriptx.cli.wav_processing_workflow.check_ffmpeg_available')
    @patch('transcriptx.cli.wav_processing_workflow.questionary.select')
    def test_wav_workflow_cancel(self, mock_select, mock_check_ffmpeg):
        """Test canceling workflow."""
        mock_check_ffmpeg.return_value = (True, None)
        mock_select.return_value.ask.return_value = "❌ Cancel"
        
        _run_wav_processing_workflow_impl()
        
        # Should return without errors
        assert True


class TestConvertWorkflow:
    """Tests for _run_convert_workflow function."""
    
    @patch('transcriptx.cli.wav_processing_workflow.select_folder_interactive')
    @patch('transcriptx.cli.wav_processing_workflow.select_wav_files_interactive')
    @patch('transcriptx.cli.wav_processing_workflow.get_audio_duration')
    @patch('transcriptx.cli.wav_processing_workflow.questionary.confirm')
    @patch('transcriptx.cli.wav_processing_workflow.convert_wav_to_mp3')
    @patch('transcriptx.cli.wav_processing_workflow.rename_mp3_after_conversion')
    def test_convert_workflow_success(
        self, mock_rename, mock_convert, mock_confirm,
        mock_duration, mock_select_files, mock_select_folder, tmp_path
    ):
        """Test successful conversion workflow."""
        folder = tmp_path / "wavs"
        folder.mkdir()
        wav_file = folder / "test.wav"
        wav_file.write_bytes(b"fake wav")
        mp3_file = tmp_path / "test.mp3"
        
        mock_select_folder.return_value = folder
        mock_select_files.return_value = [wav_file]
        mock_duration.return_value = 120.0
        mock_confirm.return_value.ask.return_value = True
        mock_convert.return_value = mp3_file
        mock_rename.return_value = mp3_file
        
        with patch('transcriptx.cli.wav_processing_workflow.Progress') as mock_progress, \
             patch('transcriptx.cli.wav_processing_workflow.print'):
            mock_progress.return_value.__enter__.return_value = MagicMock()
            _run_convert_workflow()
        
        mock_select_folder.assert_called_once()
        mock_select_files.assert_called_once()
        mock_convert.assert_called_once()
    
    @patch('transcriptx.cli.wav_processing_workflow.select_folder_interactive')
    def test_convert_workflow_no_folder(self, mock_select_folder):
        """Test when no folder is selected."""
        mock_select_folder.return_value = None
        
        _run_convert_workflow()
        
        # Should return early
        mock_select_folder.assert_called_once()
    
    @patch('transcriptx.cli.wav_processing_workflow.select_folder_interactive')
    @patch('transcriptx.cli.wav_processing_workflow.select_wav_files_interactive')
    def test_convert_workflow_no_files(
        self, mock_select_files, mock_select_folder, tmp_path
    ):
        """Test when no files are selected."""
        folder = tmp_path / "wavs"
        folder.mkdir()
        
        mock_select_folder.return_value = folder
        mock_select_files.return_value = []
        
        _run_convert_workflow()
        
        # Should handle empty selection
        mock_select_files.assert_called_once()


class TestMergeWorkflow:
    """Tests for _run_merge_workflow function."""
    
    @patch('transcriptx.cli.wav_processing_workflow.select_folder_interactive')
    @patch('transcriptx.cli.wav_processing_workflow.select_wav_files_interactive')
    @patch('transcriptx.cli.wav_processing_workflow.reorder_files_interactive')
    @patch('transcriptx.cli.wav_processing_workflow.get_audio_duration')
    @patch('transcriptx.cli.wav_processing_workflow.questionary.text')
    @patch('transcriptx.cli.wav_processing_workflow.questionary.confirm')
    @patch('transcriptx.cli.wav_processing_workflow.backup_wav_files_to_storage')
    @patch('transcriptx.cli.wav_processing_workflow.merge_wav_files')
    def test_merge_workflow_success(
        self, mock_merge, mock_backup, mock_confirm, mock_text,
        mock_duration, mock_reorder, mock_select_files, mock_select_folder, tmp_path
    ):
        """Test successful merge workflow."""
        folder = tmp_path / "wavs"
        folder.mkdir()
        wav_files = [folder / f"file{i}.wav" for i in range(2)]
        for f in wav_files:
            f.write_bytes(b"fake wav")
        
        mock_select_folder.return_value = folder
        mock_select_files.return_value = wav_files
        mock_reorder.return_value = wav_files
        mock_duration.return_value = 60.0
        mock_text.return_value.ask.return_value = "merged.mp3"
        mock_confirm.return_value.ask.side_effect = [True, True]  # Confirm merge, overwrite if needed
        mock_backup.return_value = wav_files
        mock_merge.return_value = tmp_path / "merged.mp3"
        
        with patch('transcriptx.cli.wav_processing_workflow.Progress') as mock_progress, \
             patch('transcriptx.cli.wav_processing_workflow.print'):
            mock_progress.return_value.__enter__.return_value = MagicMock()
            _run_merge_workflow()
        
        mock_select_folder.assert_called_once()
        mock_select_files.assert_called_once()
        mock_merge.assert_called_once()
    
    @patch('transcriptx.cli.wav_processing_workflow.select_folder_interactive')
    @patch('transcriptx.cli.wav_processing_workflow.select_wav_files_interactive')
    def test_merge_workflow_insufficient_files(
        self, mock_select_files, mock_select_folder, tmp_path
    ):
        """Test when less than 2 files selected."""
        folder = tmp_path / "wavs"
        folder.mkdir()
        wav_file = folder / "file.wav"
        wav_file.write_bytes(b"fake")
        
        mock_select_folder.return_value = folder
        mock_select_files.return_value = [wav_file]  # Only 1 file
        
        with patch('transcriptx.cli.wav_processing_workflow.print'):
            _run_merge_workflow()
        
        # Should handle insufficient files
        mock_select_files.assert_called_once()
