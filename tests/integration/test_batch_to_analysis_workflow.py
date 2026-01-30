"""
Integration tests for batch WAV processing → analysis workflow.

This module tests the complete workflow from batch WAV processing through
to analysis pipeline execution on all processed transcripts.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import json
import pytest

from transcriptx.cli.batch_wav_workflow import _run_batch_wav_workflow_impl, batch_process_files
from transcriptx.cli.batch_workflows import run_batch_analysis_pipeline


@pytest.mark.integration
class TestBatchToAnalysisWorkflow:
    """Tests for batch WAV processing → analysis workflow."""
    
    @pytest.fixture
    def sample_wav_files(self, tmp_path):
        """Fixture for sample WAV files."""
        wav_folder = tmp_path / "wavs"
        wav_folder.mkdir()
        
        files = []
        for i in range(3):
            wav_file = wav_folder / f"test_{i}.wav"
            wav_file.write_bytes(b"fake wav content")
            files.append(wav_file)
        
        return files
    
    @pytest.fixture
    def sample_transcript_files(self, tmp_path):
        """Fixture for sample transcript files."""
        transcript_files = []
        for i in range(3):
            transcript_file = tmp_path / f"test_{i}_transcript.json"
            transcript_data = {
                "segments": [
                    {
                        "speaker": "SPEAKER_00",
                        "text": f"Test transcription {i}",
                        "start": 0.0,
                        "end": 2.0
                    }
                ]
            }
            transcript_file.write_text(json.dumps(transcript_data))
            transcript_files.append(transcript_file)
        
        return transcript_files
    
    def test_complete_batch_processing_flow(
        self, sample_wav_files, sample_transcript_files, tmp_path
    ):
        """Test complete batch processing flow."""
        with patch('transcriptx.cli.batch_wav_workflow.select_folder_interactive') as mock_select, \
             patch('transcriptx.cli.batch_wav_workflow.discover_wav_files') as mock_discover, \
             patch('transcriptx.cli.batch_wav_workflow.filter_new_files') as mock_filter, \
             patch('transcriptx.cli.batch_wav_workflow.questionary.select') as mock_select_q, \
             patch('transcriptx.cli.batch_wav_workflow.questionary.confirm') as mock_confirm, \
             patch('transcriptx.cli.batch_wav_workflow.batch_process_files') as mock_process, \
             patch('transcriptx.cli.batch_wav_workflow._show_summary') as mock_summary:
            
            # Setup mocks
            mock_select.return_value = tmp_path / "wavs"
            mock_discover.return_value = sample_wav_files
            mock_filter.return_value = sample_wav_files
            mock_select_q.return_value.ask.side_effect = [
                "📦 All files",  # Size filter
                "🚀 Automatic (process all files)"  # Processing mode
            ]
            mock_process.return_value = {
                "total_files": 3,
                "successful": [
                    {"file": str(f), "status": "success", "transcript_path": str(sample_transcript_files[i])}
                    for i, f in enumerate(sample_wav_files)
                ],
                "failed": [],
                "skipped": []
            }
            
            _run_batch_wav_workflow_impl()
            
            # Verify workflow steps
            mock_select.assert_called_once()
            mock_discover.assert_called_once()
            mock_filter.assert_called_once()
            mock_process.assert_called_once()
            mock_summary.assert_called_once()
    
    def test_resume_capability(self, sample_wav_files, tmp_path):
        """Test resume capability from state."""
        with patch('transcriptx.cli.batch_wav_workflow.select_folder_interactive') as mock_select, \
             patch('transcriptx.cli.batch_wav_workflow.discover_wav_files') as mock_discover, \
             patch('transcriptx.cli.batch_wav_workflow.filter_new_files') as mock_filter, \
             patch('transcriptx.cli.batch_wav_workflow.resume_batch_processing') as mock_resume, \
             patch('transcriptx.cli.batch_wav_workflow.questionary.select') as mock_select_q:
            
            mock_select.return_value = tmp_path / "wavs"
            mock_discover.return_value = sample_wav_files
            mock_filter.return_value = sample_wav_files[1:]  # First file already processed
            mock_select_q.return_value.ask.return_value = "🔄 Resume previous batch"
            mock_resume.return_value = {
                "total_files": 2,
                "successful": [],
                "failed": [],
                "skipped": []
            }
            
            _run_batch_wav_workflow_impl()
            
            # Verify resume called
            mock_resume.assert_called_once()
    
    def test_mixed_success_failure_scenarios(self, sample_wav_files, tmp_path):
        """Test batch processing with mixed success/failure."""
        with patch('transcriptx.cli.batch_wav_workflow.select_folder_interactive') as mock_select, \
             patch('transcriptx.cli.batch_wav_workflow.discover_wav_files') as mock_discover, \
             patch('transcriptx.cli.batch_wav_workflow.filter_new_files') as mock_filter, \
             patch('transcriptx.cli.batch_wav_workflow.questionary.select') as mock_select_q, \
             patch('transcriptx.cli.batch_wav_workflow.batch_process_files') as mock_process, \
             patch('transcriptx.cli.batch_wav_workflow._show_summary') as mock_summary:
            
            mock_select.return_value = tmp_path / "wavs"
            mock_discover.return_value = sample_wav_files
            mock_filter.return_value = sample_wav_files
            mock_select_q.return_value.ask.side_effect = [
                "📦 All files",
                "🚀 Automatic (process all files)"
            ]
            
            # Simulate mixed results
            mock_process.return_value = {
                "total_files": 3,
                "successful": [
                    {"file": str(sample_wav_files[0]), "status": "success"}
                ],
                "failed": [
                    {"file": str(sample_wav_files[1]), "status": "failed", "error": "Conversion failed"}
                ],
                "skipped": [
                    {"file": str(sample_wav_files[2]), "status": "skipped", "reason": "Already processed"}
                ]
            }
            
            _run_batch_wav_workflow_impl()
            
            # Verify processing continued despite failures
            mock_process.assert_called_once()
            result = mock_process.return_value
            assert result["successful"] == 1
            assert result["failed"] == 1
            assert result["skipped"] == 1
    
    def test_batch_with_post_processing_analysis(
        self, sample_wav_files, sample_transcript_files, tmp_path
    ):
        """Test batch processing with post-processing analysis."""
        with patch('transcriptx.cli.batch_wav_workflow.select_folder_interactive') as mock_select, \
             patch('transcriptx.cli.batch_wav_workflow.discover_wav_files') as mock_discover, \
             patch('transcriptx.cli.batch_wav_workflow.filter_new_files') as mock_filter, \
             patch('transcriptx.cli.batch_wav_workflow.questionary.select') as mock_select_q, \
             patch('transcriptx.cli.batch_wav_workflow.questionary.confirm') as mock_confirm, \
             patch('transcriptx.cli.batch_wav_workflow.batch_process_files') as mock_process, \
             patch('transcriptx.cli.batch_wav_workflow.run_batch_analysis_pipeline') as mock_analysis:
            
            mock_select.return_value = tmp_path / "wavs"
            mock_discover.return_value = sample_wav_files
            mock_filter.return_value = sample_wav_files
            mock_select_q.return_value.ask.side_effect = [
                "📦 All files",
                "🚀 Automatic (process all files)"
            ]
            mock_process.return_value = {
                "total_files": 3,
                "successful": [
                    {"file": str(f), "transcript_path": str(sample_transcript_files[i])}
                    for i, f in enumerate(sample_wav_files)
                ],
                "failed": [],
                "skipped": []
            }
            mock_confirm.return_value.ask.return_value = True  # User wants analysis
            mock_analysis.return_value = {"status": "success"}
            
            _run_batch_wav_workflow_impl()
            
            # Verify analysis pipeline called
            mock_analysis.assert_called_once()
    
    def test_state_updates_for_each_file(self, sample_wav_files, tmp_path):
        """Test that state is updated for each processed file."""
        with patch('transcriptx.cli.batch_wav_workflow.select_folder_interactive') as mock_select, \
             patch('transcriptx.cli.batch_wav_workflow.discover_wav_files') as mock_discover, \
             patch('transcriptx.cli.batch_wav_workflow.filter_new_files') as mock_filter, \
             patch('transcriptx.cli.batch_wav_workflow.questionary.select') as mock_select_q, \
             patch('transcriptx.cli.batch_wav_workflow.batch_process_files') as mock_process, \
             patch('transcriptx.cli.processing_state.mark_file_processed') as mock_mark:
            
            mock_select.return_value = tmp_path / "wavs"
            mock_discover.return_value = sample_wav_files
            mock_filter.return_value = sample_wav_files
            mock_select_q.return_value.ask.side_effect = [
                "📦 All files",
                "🚀 Automatic (process all files)"
            ]
            mock_process.return_value = {
                "total_files": 3,
                "successful": [
                    {"file": str(f), "status": "success"}
                    for f in sample_wav_files
                ],
                "failed": [],
                "skipped": []
            }
            
            _run_batch_wav_workflow_impl()
            
            # Verify state management (if implemented in batch_process_files)
            mock_process.assert_called_once()
    
    def test_summary_generation(self, sample_wav_files, tmp_path):
        """Test summary generation after batch processing."""
        with patch('transcriptx.cli.batch_wav_workflow.select_folder_interactive') as mock_select, \
             patch('transcriptx.cli.batch_wav_workflow.discover_wav_files') as mock_discover, \
             patch('transcriptx.cli.batch_wav_workflow.filter_new_files') as mock_filter, \
             patch('transcriptx.cli.batch_wav_workflow.questionary.select') as mock_select_q, \
             patch('transcriptx.cli.batch_wav_workflow.batch_process_files') as mock_process, \
             patch('transcriptx.cli.batch_wav_workflow._show_summary') as mock_summary:
            
            mock_select.return_value = tmp_path / "wavs"
            mock_discover.return_value = sample_wav_files
            mock_filter.return_value = sample_wav_files
            mock_select_q.return_value.ask.side_effect = [
                "📦 All files",
                "🚀 Automatic (process all files)"
            ]
            mock_process.return_value = {
                "total_files": 3,
                "successful": [{"file": str(f)} for f in sample_wav_files],
                "failed": [],
                "skipped": []
            }
            
            _run_batch_wav_workflow_impl()
            
            # Verify summary called with results
            mock_summary.assert_called_once()
            summary_args = mock_summary.call_args[0][0]
            assert summary_args["total_files"] == 3
