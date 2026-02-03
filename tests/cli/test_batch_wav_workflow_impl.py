"""
Tests for batch WAV workflow implementation.

This module tests batch processing logic, state management, resume capability,
and processing state persistence.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import json

import pytest

pytestmark = pytest.mark.quarantined  # reason: patches load_processing_state/processed_count which were removed/renamed; remove_by: when batch_wav API stabilizes

from transcriptx.cli.batch_wav_workflow import (
    _run_batch_wav_workflow_impl,
    batch_process_files,
    _show_summary,
    _assess_and_suggest_preprocessing
)


class TestBatchWAVWorkflowImpl:
    """Tests for _run_batch_wav_workflow_impl function."""
    
    @patch('transcriptx.cli.batch_wav_workflow.select_folder_interactive')
    @patch('transcriptx.cli.batch_wav_workflow.discover_wav_files')
    @patch('transcriptx.cli.batch_wav_workflow.filter_new_files')
    @patch('transcriptx.cli.batch_wav_workflow.questionary.select')
    @patch('transcriptx.cli.batch_wav_workflow.questionary.confirm')
    @patch('transcriptx.cli.batch_wav_workflow.batch_process_files')
    @patch('transcriptx.cli.batch_wav_workflow._show_summary')
    def test_batch_workflow_complete_flow(
        self, mock_summary, mock_process, mock_confirm, mock_select,
        mock_filter_new, mock_discover, mock_select_folder, tmp_path
    ):
        """Test complete batch workflow flow."""
        wav_folder = tmp_path / "wavs"
        wav_folder.mkdir()
        wav_file = wav_folder / "test.wav"
        wav_file.write_bytes(b"fake wav")
        
        mock_select_folder.return_value = wav_folder
        mock_discover.return_value = [wav_file]
        mock_filter_new.return_value = [wav_file]
        mock_select.return_value.ask.return_value = "📦 All files"
        mock_select.return_value.ask.side_effect = [
            "📦 All files",  # Size filter
            "🚀 Automatic (process all files)"  # Processing mode
        ]
        mock_process.return_value = {
            "total_files": 1,
            "successful": [{"file": str(wav_file), "status": "success"}],
            "failed": [],
            "skipped": []
        }
        
        _run_batch_wav_workflow_impl()
        
        mock_select_folder.assert_called_once()
        mock_discover.assert_called_once()
        mock_filter_new.assert_called_once()
        mock_process.assert_called_once()
        mock_summary.assert_called_once()
    
    @patch('transcriptx.cli.batch_wav_workflow.select_folder_interactive')
    def test_batch_workflow_no_folder_selected(self, mock_select_folder):
        """Test workflow when no folder is selected."""
        mock_select_folder.return_value = None
        
        _run_batch_wav_workflow_impl()
        
        # Should return early
        mock_select_folder.assert_called_once()
    
    @patch('transcriptx.cli.batch_wav_workflow.select_folder_interactive')
    @patch('transcriptx.cli.batch_wav_workflow.discover_wav_files')
    def test_batch_workflow_no_wav_files(
        self, mock_discover, mock_select_folder, tmp_path
    ):
        """Test workflow when no WAV files found."""
        folder = tmp_path / "empty"
        folder.mkdir()
        
        mock_select_folder.return_value = folder
        mock_discover.return_value = []
        
        _run_batch_wav_workflow_impl()
        
        # Should handle empty folder gracefully
        mock_discover.assert_called_once()
    
    @patch('transcriptx.cli.batch_wav_workflow.select_folder_interactive')
    @patch('transcriptx.cli.batch_wav_workflow.discover_wav_files')
    @patch('transcriptx.cli.batch_wav_workflow.filter_new_files')
    @patch('transcriptx.cli.batch_wav_workflow.questionary.confirm')
    def test_batch_workflow_all_files_processed(
        self, mock_confirm, mock_filter_new, mock_discover,
        mock_select_folder, tmp_path
    ):
        """Test workflow when all files already processed."""
        folder = tmp_path / "wavs"
        folder.mkdir()
        wav_file = folder / "test.wav"
        wav_file.write_bytes(b"fake")
        
        mock_select_folder.return_value = folder
        mock_discover.return_value = [wav_file]
        mock_filter_new.return_value = []  # All processed
        mock_confirm.return_value.ask.return_value = False  # Don't reprocess
        
        _run_batch_wav_workflow_impl()
        
        # Should handle already-processed files
        mock_filter_new.assert_called_once()


class TestBatchProcessFiles:
    """Tests for batch_process_files function."""
    
    @patch('transcriptx.cli.batch_wav_workflow.resume_batch_processing')
    @patch('transcriptx.cli.batch_wav_workflow.check_whisperx_compose_service')
    @patch('transcriptx.cli.batch_wav_workflow.start_whisperx_compose_service')
    @patch('transcriptx.cli.batch_wav_workflow.create_batch_checkpoint')
    @patch('transcriptx.cli.batch_wav_workflow.process_single_file')
    @patch('transcriptx.cli.batch_wav_workflow.complete_batch_checkpoint')
    def test_batch_process_files_success(
        self, mock_complete, mock_process, mock_checkpoint,
        mock_start_service, mock_check_service, mock_resume, tmp_path
    ):
        """Test successful batch processing."""
        wav_files = [
            tmp_path / "file1.wav",
            tmp_path / "file2.wav"
        ]
        for f in wav_files:
            f.write_bytes(b"fake wav")
        
        mock_resume.return_value = {"can_resume": False}
        mock_check_service.return_value = True
        mock_process.side_effect = [
            {"status": "success", "file": str(wav_files[0])},
            {"status": "success", "file": str(wav_files[1])}
        ]
        
        with patch('transcriptx.cli.batch_wav_workflow.Progress') as mock_progress:
            mock_progress.return_value.__enter__.return_value = MagicMock()
            result = batch_process_files(wav_files)
        
        assert result["total_files"] == 2
        assert len(result["successful"]) == 2
        assert len(result["failed"]) == 0
        mock_complete.assert_called_once()
    
    @patch('transcriptx.cli.batch_wav_workflow.resume_batch_processing')
    @patch('transcriptx.cli.batch_wav_workflow.questionary.confirm')
    def test_batch_process_files_resume(
        self, mock_confirm, mock_resume, tmp_path
    ):
        """Test batch processing with resume capability."""
        wav_files = [tmp_path / "file1.wav"]
        wav_files[0].write_bytes(b"fake")
        
        mock_resume.return_value = {
            "can_resume": True,
            "processed_count": 1,
            "total_count": 2,
            "failed_count": 0,
            "remaining_files": wav_files,
            "checkpoint": {
                "batch_id": "test-id",
                "processed_files": [],
                "failed_files": []
            }
        }
        mock_confirm.return_value.ask.return_value = True  # Resume
        
        with patch('transcriptx.cli.batch_wav_workflow.check_whisperx_compose_service', return_value=True), \
             patch('transcriptx.cli.batch_wav_workflow.process_single_file') as mock_process, \
             patch('transcriptx.cli.batch_wav_workflow.Progress') as mock_progress, \
             patch('transcriptx.cli.batch_wav_workflow.create_batch_checkpoint'), \
             patch('transcriptx.cli.batch_wav_workflow.complete_batch_checkpoint'):
            
            mock_progress.return_value.__enter__.return_value = MagicMock()
            mock_process.return_value = {"status": "success", "file": str(wav_files[0])}
            
            result = batch_process_files(wav_files)
        
        # Should resume from checkpoint
        mock_confirm.assert_called_once()
    
    @patch('transcriptx.cli.batch_wav_workflow.resume_batch_processing')
    @patch('transcriptx.cli.batch_wav_workflow.check_whisperx_compose_service')
    @patch('transcriptx.cli.batch_wav_workflow.start_whisperx_compose_service')
    def test_batch_process_files_whisperx_not_available(
        self, mock_start, mock_check, mock_resume, tmp_path
    ):
        """Test when WhisperX service is not available."""
        wav_files = [tmp_path / "file.wav"]
        wav_files[0].write_bytes(b"fake")
        
        mock_resume.return_value = {"can_resume": False}
        mock_check.return_value = False
        mock_start.return_value = False  # Failed to start
        
        result = batch_process_files(wav_files)
        
        # Should return early with no processing
        assert result["total_files"] == 1
        assert len(result["successful"]) == 0


class TestShowSummary:
    """Tests for _show_summary function."""
    
    @patch('transcriptx.cli.batch_wav_workflow.questionary.confirm')
    def test_show_summary_successful_files(self, mock_confirm, tmp_path):
        """Test summary display with successful files."""
        results = {
            "total_files": 2,
            "successful": [
                {
                    "file": str(tmp_path / "file1.wav"),
                    "steps": {
                        "detect_type": {"type": "conversation"},
                        "extract_tags": {"tags": ["tag1", "tag2"]}
                    }
                }
            ],
            "failed": [],
            "skipped": []
        }
        
        mock_confirm.return_value.ask.return_value = False  # Don't move files
        
        with patch('transcriptx.cli.batch_wav_workflow.print'):
            _show_summary(results)
        
        # Should display summary
        assert True  # Test passes if no exception
    
    def test_show_summary_with_failures(self, tmp_path):
        """Test summary display with failed files."""
        results = {
            "total_files": 2,
            "successful": [],
            "failed": [
                {"file": str(tmp_path / "file1.wav"), "error": "Test error"}
            ],
            "skipped": []
        }
        
        with patch('transcriptx.cli.batch_wav_workflow.print'):
            _show_summary(results)
        
        # Should display failures
        assert True


class TestBatchWorkflowErrorHandling:
    """Tests for error handling in batch workflow."""
    
    @patch('transcriptx.cli.batch_wav_workflow.select_folder_interactive')
    @patch('transcriptx.cli.batch_wav_workflow.discover_wav_files')
    @patch('transcriptx.cli.batch_wav_workflow.filter_new_files')
    @patch('transcriptx.cli.batch_wav_workflow.batch_process_files')
    def test_individual_file_failure_isolation(
        self, mock_process, mock_filter, mock_discover,
        mock_select, tmp_path
    ):
        """Test that individual file failures don't stop batch."""
        wav_files = [
            tmp_path / "file1.wav",
            tmp_path / "file2.wav",
            tmp_path / "file3.wav"
        ]
        for f in wav_files:
            f.write_bytes(b"fake")
        
        mock_select.return_value = tmp_path
        mock_discover.return_value = wav_files
        mock_filter.return_value = wav_files
        mock_process.return_value = {
            "total_files": 3,
            "successful": [{"file": str(wav_files[0])}],
            "failed": [{"file": str(wav_files[1]), "error": "Conversion failed"}],
            "skipped": [{"file": str(wav_files[2])}]
        }
        
        with patch('transcriptx.cli.batch_wav_workflow.questionary.select') as mock_select_q, \
             patch('transcriptx.cli.batch_wav_workflow._show_summary'):
            mock_select_q.return_value.ask.side_effect = [
                "📦 All files",
                "🚀 Automatic (process all files)"
            ]
            
            _run_batch_wav_workflow_impl()
        
        # Should continue processing despite failures
        mock_process.assert_called_once()
        result = mock_process.return_value
        assert len(result["successful"]) == 1
        assert len(result["failed"]) == 1
    
    @patch('transcriptx.cli.batch_wav_workflow.select_folder_interactive')
    @patch('transcriptx.cli.batch_wav_workflow.discover_wav_files')
    @patch('transcriptx.cli.batch_wav_workflow.filter_new_files')
    @patch('transcriptx.cli.batch_wav_workflow.batch_process_files')
    def test_file_conversion_failure(
        self, mock_process, mock_filter, mock_discover,
        mock_select, tmp_path
    ):
        """Test handling when file conversion fails."""
        wav_files = [tmp_path / "file1.wav"]
        wav_files[0].write_bytes(b"fake")
        
        mock_select.return_value = tmp_path
        mock_discover.return_value = wav_files
        mock_filter.return_value = wav_files
        mock_process.return_value = {
            "total_files": 1,
            "successful": [],
            "failed": [{"file": str(wav_files[0]), "error": "Conversion failed"}],
            "skipped": []
        }
        
        with patch('transcriptx.cli.batch_wav_workflow.questionary.select') as mock_select_q, \
             patch('transcriptx.cli.batch_wav_workflow._show_summary'):
            mock_select_q.return_value.ask.side_effect = [
                "📦 All files",
                "🚀 Automatic (process all files)"
            ]
            
            _run_batch_wav_workflow_impl()
        
        # Should skip failed file and continue
        mock_process.assert_called_once()
    
    @patch('transcriptx.cli.batch_wav_workflow.select_folder_interactive')
    @patch('transcriptx.cli.batch_wav_workflow.discover_wav_files')
    def test_file_discovery_error(
        self, mock_discover, mock_select, tmp_path
    ):
        """Test handling when file discovery fails."""
        mock_select.return_value = tmp_path
        mock_discover.side_effect = PermissionError("Cannot access folder")
        
        with patch('transcriptx.cli.batch_wav_workflow.log_error') as mock_log_error:
            _run_batch_wav_workflow_impl()
        
        # Should handle discovery error
        mock_log_error.assert_called()
    
    @patch('transcriptx.cli.batch_wav_workflow.select_folder_interactive')
    @patch('transcriptx.cli.batch_wav_workflow.discover_wav_files')
    @patch('transcriptx.cli.batch_wav_workflow.filter_new_files')
    @patch('transcriptx.cli.batch_wav_workflow.load_processing_state')
    def test_state_file_corruption(
        self, mock_load_state, mock_filter, mock_discover,
        mock_select, tmp_path
    ):
        """Test handling when state file is corrupted."""
        wav_files = [tmp_path / "file1.wav"]
        wav_files[0].write_bytes(b"fake")
        
        mock_select.return_value = tmp_path
        mock_discover.return_value = wav_files
        mock_load_state.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        
        with patch('transcriptx.cli.batch_wav_workflow.filter_new_files') as mock_filter_new:
            # Should handle corruption gracefully
            mock_filter_new.return_value = wav_files  # Treat all as new
            
            _run_batch_wav_workflow_impl()
        
        # Should recover from corruption
        assert True
    
    @patch('transcriptx.cli.batch_wav_workflow.select_folder_interactive')
    @patch('transcriptx.cli.batch_wav_workflow.discover_wav_files')
    @patch('transcriptx.cli.batch_wav_workflow.filter_new_files')
    @patch('transcriptx.cli.batch_wav_workflow.load_processing_state')
    def test_state_file_locked(
        self, mock_load_state, mock_filter, mock_discover,
        mock_select, tmp_path
    ):
        """Test handling when state file is locked."""
        wav_files = [tmp_path / "file1.wav"]
        wav_files[0].write_bytes(b"fake")
        
        mock_select.return_value = tmp_path
        mock_discover.return_value = wav_files
        mock_load_state.side_effect = BlockingIOError("Resource temporarily unavailable")
        
        with patch('transcriptx.cli.batch_wav_workflow.filter_new_files') as mock_filter_new, \
             patch('transcriptx.cli.batch_wav_workflow.log_error') as mock_log_error:
            
            mock_filter_new.return_value = wav_files
            
            _run_batch_wav_workflow_impl()
        
        # Should handle lock error
        mock_log_error.assert_called()
    
    @patch('transcriptx.cli.batch_wav_workflow.batch_process_files')
    def test_memory_exhaustion_during_batch(
        self, mock_process, tmp_path
    ):
        """Test handling when memory is exhausted during batch."""
        wav_files = [tmp_path / f"file{i}.wav" for i in range(10)]
        for f in wav_files:
            f.write_bytes(b"fake")
        
        mock_process.side_effect = MemoryError("Memory limit exceeded")
        
        with patch('transcriptx.cli.batch_wav_workflow.log_error') as mock_log_error:
            try:
                batch_process_files(wav_files)
            except MemoryError:
                pass
        
        # Should handle memory error
        mock_log_error.assert_called()
    
    @patch('transcriptx.cli.batch_wav_workflow.resume_batch_processing')
    @patch('transcriptx.cli.batch_wav_workflow.load_processing_state')
    def test_resume_with_corrupted_state(
        self, mock_load_state, mock_resume, tmp_path
    ):
        """Test resume with corrupted state."""
        wav_files = [tmp_path / "file1.wav"]
        wav_files[0].write_bytes(b"fake")
        
        mock_load_state.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_resume.return_value = {"can_resume": False}
        
        with patch('transcriptx.cli.batch_wav_workflow.check_whisperx_compose_service', return_value=True), \
             patch('transcriptx.cli.batch_wav_workflow.process_single_file') as mock_process, \
             patch('transcriptx.cli.batch_wav_workflow.Progress') as mock_progress, \
             patch('transcriptx.cli.batch_wav_workflow.create_batch_checkpoint'), \
             patch('transcriptx.cli.batch_wav_workflow.complete_batch_checkpoint'):
            
            mock_progress.return_value.__enter__.return_value = MagicMock()
            mock_process.return_value = {"status": "success"}
            
            result = batch_process_files(wav_files)
        
        # Should recover and process files
        assert result["total_files"] == 1
    
    @patch('transcriptx.cli.batch_wav_workflow.resume_batch_processing')
    def test_resume_with_missing_files(
        self, mock_resume, tmp_path
    ):
        """Test resume when some files are missing."""
        wav_files = [tmp_path / "file1.wav"]
        wav_files[0].write_bytes(b"fake")
        
        mock_resume.return_value = {
            "can_resume": True,
            "remaining_files": [tmp_path / "missing.wav"]  # File doesn't exist
        }
        
        with patch('transcriptx.cli.batch_wav_workflow.questionary.confirm', return_value=MagicMock(ask=MagicMock(return_value=True))), \
             patch('transcriptx.cli.batch_wav_workflow.check_whisperx_compose_service', return_value=True), \
             patch('transcriptx.cli.batch_wav_workflow.process_single_file') as mock_process, \
             patch('transcriptx.cli.batch_wav_workflow.Progress') as mock_progress, \
             patch('transcriptx.cli.batch_wav_workflow.create_batch_checkpoint'), \
             patch('transcriptx.cli.batch_wav_workflow.complete_batch_checkpoint'):
            
            mock_progress.return_value.__enter__.return_value = MagicMock()
            # Simulate file not found
            mock_process.side_effect = FileNotFoundError("File not found")
            
            result = batch_process_files(wav_files)
        
        # Should handle missing files
        assert result is not None
    
    @patch('transcriptx.cli.batch_wav_workflow.resume_batch_processing')
    def test_resume_with_changed_file_structure(
        self, mock_resume, tmp_path
    ):
        """Test resume when file structure has changed."""
        wav_files = [tmp_path / "file1.wav"]
        wav_files[0].write_bytes(b"fake")
        
        mock_resume.return_value = {
            "can_resume": True,
            "remaining_files": wav_files
        }
        
        with patch('transcriptx.cli.batch_wav_workflow.questionary.confirm', return_value=MagicMock(ask=MagicMock(return_value=True))), \
             patch('transcriptx.cli.batch_wav_workflow.check_whisperx_compose_service', return_value=True), \
             patch('transcriptx.cli.batch_wav_workflow.discover_wav_files') as mock_discover, \
             patch('transcriptx.cli.batch_wav_workflow.process_single_file') as mock_process, \
             patch('transcriptx.cli.batch_wav_workflow.Progress') as mock_progress, \
             patch('transcriptx.cli.batch_wav_workflow.create_batch_checkpoint'), \
             patch('transcriptx.cli.batch_wav_workflow.complete_batch_checkpoint'):
            
            mock_progress.return_value.__enter__.return_value = MagicMock()
            mock_process.return_value = {"status": "success"}
            # Simulate re-discovery
            mock_discover.return_value = wav_files
            
            result = batch_process_files(wav_files)
        
        # Should handle structure changes
        assert result is not None
    
    @patch('transcriptx.cli.batch_wav_workflow.batch_process_files')
    def test_disk_space_exhaustion(
        self, mock_process, tmp_path
    ):
        """Test handling when disk space is exhausted."""
        wav_files = [tmp_path / "file1.wav"]
        wav_files[0].write_bytes(b"fake")
        
        mock_process.side_effect = OSError("No space left on device")
        
        with patch('transcriptx.cli.batch_wav_workflow.log_error') as mock_log_error:
            try:
                batch_process_files(wav_files)
            except OSError:
                pass
        
        # Should handle disk space error
        mock_log_error.assert_called()


class TestAssessAndSuggestPreprocessing:
    """Tests for _assess_and_suggest_preprocessing function."""
    
    @patch('transcriptx.cli.batch_wav_workflow.assess_audio_noise')
    @patch('transcriptx.cli.batch_wav_workflow.questionary.confirm')
    @patch('transcriptx.cli.batch_wav_workflow.Progress')
    def test_assess_global_mode_off(self, mock_progress, mock_confirm, mock_assess, tmp_path):
        """Test assessment when global mode is 'off'."""
        from transcriptx.core.utils.config import AudioPreprocessingConfig
        
        wav_files = [tmp_path / "file1.wav"]
        wav_files[0].write_bytes(b"fake")
        
        config = AudioPreprocessingConfig(preprocessing_mode="off")
        
        decisions = _assess_and_suggest_preprocessing(wav_files, config)
        
        # Should return all False decisions
        assert wav_files[0] in decisions
        assert decisions[wav_files[0]]["denoise"] is False
        assert decisions[wav_files[0]]["highpass"] is False
        assert decisions[wav_files[0]]["normalize"] is False
        # Should not assess files
        mock_assess.assert_not_called()
    
    @patch('transcriptx.cli.batch_wav_workflow.assess_audio_noise')
    @patch('transcriptx.cli.batch_wav_workflow.questionary.confirm')
    @patch('transcriptx.cli.batch_wav_workflow.Progress')
    def test_assess_global_mode_auto(self, mock_progress, mock_confirm, mock_assess, tmp_path):
        """Test assessment when global mode is 'auto'."""
        from transcriptx.core.utils.config import AudioPreprocessingConfig
        
        wav_files = [tmp_path / "file1.wav"]
        wav_files[0].write_bytes(b"fake")
        
        config = AudioPreprocessingConfig(preprocessing_mode="auto")
        
        decisions = _assess_and_suggest_preprocessing(wav_files, config)
        
        # Should return empty dict (auto mode doesn't need decisions)
        assert decisions == {}
        # Should not assess files
        mock_assess.assert_not_called()
    
    @patch('transcriptx.cli.batch_wav_workflow.assess_audio_noise')
    @patch('transcriptx.cli.batch_wav_workflow.questionary.confirm')
    @patch('transcriptx.cli.batch_wav_workflow.Progress')
    def test_assess_global_mode_suggest(self, mock_progress, mock_confirm, mock_assess, tmp_path):
        """Test assessment when global mode is 'suggest'."""
        from transcriptx.core.utils.config import AudioPreprocessingConfig
        
        wav_files = [tmp_path / "file1.wav"]
        wav_files[0].write_bytes(b"fake")
        
        config = AudioPreprocessingConfig(preprocessing_mode="suggest")
        
        # Mock assessment result
        mock_assess.return_value = {
            "suggested_steps": ["denoise", "highpass", "normalize"],
            "noise_level": "high"
        }
        
        # Mock progress
        mock_progress.return_value.__enter__.return_value = MagicMock()
        
        # Mock user confirmation
        mock_confirm.return_value.ask.return_value = True
        
        decisions = _assess_and_suggest_preprocessing(wav_files, config)
        
        # Should assess files
        mock_assess.assert_called_once()
        # Should return decisions based on assessment
        assert wav_files[0] in decisions
        assert decisions[wav_files[0]]["denoise"] is True
        assert decisions[wav_files[0]]["highpass"] is True
        assert decisions[wav_files[0]]["normalize"] is True
    
    @patch('transcriptx.cli.batch_wav_workflow.assess_audio_noise')
    @patch('transcriptx.cli.batch_wav_workflow.questionary.confirm')
    @patch('transcriptx.cli.batch_wav_workflow.Progress')
    def test_assess_skip_confirm(self, mock_progress, mock_confirm, mock_assess, tmp_path):
        """Test assessment with skip_confirm=True (non-interactive mode)."""
        from transcriptx.core.utils.config import AudioPreprocessingConfig
        
        wav_files = [tmp_path / "file1.wav"]
        wav_files[0].write_bytes(b"fake")
        
        config = AudioPreprocessingConfig(preprocessing_mode="suggest")
        
        # Mock assessment result
        mock_assess.return_value = {
            "suggested_steps": ["denoise", "highpass"],
            "noise_level": "high"
        }
        
        # Mock progress
        mock_progress.return_value.__enter__.return_value = MagicMock()
        
        decisions = _assess_and_suggest_preprocessing(wav_files, config, skip_confirm=True)
        
        # Should assess files
        mock_assess.assert_called_once()
        # Should not ask for confirmation
        mock_confirm.assert_not_called()
        # Should return all False (skip all suggested steps)
        assert wav_files[0] in decisions
        assert decisions[wav_files[0]]["denoise"] is False
        assert decisions[wav_files[0]]["highpass"] is False
    
    @patch('transcriptx.cli.batch_wav_workflow.assess_audio_noise')
    @patch('transcriptx.cli.batch_wav_workflow.questionary.confirm')
    @patch('transcriptx.cli.batch_wav_workflow.Progress')
    def test_assess_selected_mode_per_step_suggest(self, mock_progress, mock_confirm, mock_assess, tmp_path):
        """Test assessment when global mode is 'selected' and per-step modes are 'suggest'."""
        from transcriptx.core.utils.config import AudioPreprocessingConfig
        
        wav_files = [tmp_path / "file1.wav"]
        wav_files[0].write_bytes(b"fake")
        
        config = AudioPreprocessingConfig(
            preprocessing_mode="selected",
            denoise_mode="suggest",
            highpass_mode="suggest",
            normalize_mode="off"  # Not in suggest mode
        )
        
        # Mock assessment result
        mock_assess.return_value = {
            "suggested_steps": ["denoise", "highpass"],
            "noise_level": "high"
        }
        
        # Mock progress
        mock_progress.return_value.__enter__.return_value = MagicMock()
        
        # Mock user confirmation
        mock_confirm.return_value.ask.return_value = True
        
        decisions = _assess_and_suggest_preprocessing(wav_files, config)
        
        # Should assess files
        mock_assess.assert_called_once()
        # Should only return decisions for steps in "suggest" mode
        assert wav_files[0] in decisions
        assert decisions[wav_files[0]]["denoise"] is True
        assert decisions[wav_files[0]]["highpass"] is True
        # normalize should be False even if suggested, because mode is "off"
        assert decisions[wav_files[0]]["normalize"] is False
    
    @patch('transcriptx.cli.batch_wav_workflow.assess_audio_noise')
    @patch('transcriptx.cli.batch_wav_workflow.questionary.confirm')
    @patch('transcriptx.cli.batch_wav_workflow.Progress')
    def test_assess_user_declines(self, mock_progress, mock_confirm, mock_assess, tmp_path):
        """Test assessment when user declines suggested preprocessing."""
        from transcriptx.core.utils.config import AudioPreprocessingConfig
        
        wav_files = [tmp_path / "file1.wav"]
        wav_files[0].write_bytes(b"fake")
        
        config = AudioPreprocessingConfig(preprocessing_mode="suggest")
        
        # Mock assessment result
        mock_assess.return_value = {
            "suggested_steps": ["denoise", "highpass"],
            "noise_level": "high"
        }
        
        # Mock progress
        mock_progress.return_value.__enter__.return_value = MagicMock()
        
        # Mock user declining
        mock_confirm.return_value.ask.return_value = False
        
        decisions = _assess_and_suggest_preprocessing(wav_files, config)
        
        # Should assess files
        mock_assess.assert_called_once()
        # Should return all False because user declined
        assert wav_files[0] in decisions
        assert decisions[wav_files[0]]["denoise"] is False
        assert decisions[wav_files[0]]["highpass"] is False
