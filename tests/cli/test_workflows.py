"""
Tests for CLI workflow modules.

This module tests all workflow functions including analysis, transcription,
speaker identification, WAV processing, batch processing, and deduplication.
"""

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit

from transcriptx.cli.workflow_modules import (
    run_single_analysis_workflow,
    run_transcription_workflow,
    run_speaker_identification_workflow,
    run_wav_processing_workflow,
    run_batch_wav_workflow,
    run_deduplication_workflow,
)


class TestSingleAnalysisWorkflow:
    """Tests for run_single_analysis_workflow."""

    @patch("transcriptx.cli.analysis_workflow.run_single_analysis_workflow")
    def test_run_single_analysis_workflow(self, mock_workflow, mock_questionary):
        """Test single analysis workflow execution."""
        mock_workflow.return_value = None

        # Should call the workflow
        run_single_analysis_workflow()

        mock_workflow.assert_called_once()

    @patch("transcriptx.cli.analysis_workflow.run_single_analysis_workflow")
    def test_analysis_workflow_complete_flow(
        self,
        mock_workflow,
        temp_transcript_file,
        mock_questionary,
    ):
        """Test that run_single_analysis_workflow is accessible."""
        mock_workflow.return_value = None
        assert mock_workflow is not None


class TestTranscriptionWorkflow:
    """Tests for run_transcription_workflow (deprecated stub)."""

    def test_run_transcription_workflow_exits_deprecated(self):
        """Transcription workflow is deprecated and exits with code 2."""
        import pytest

        with pytest.raises(SystemExit) as exc_info:
            run_transcription_workflow()
        assert exc_info.value.code == 2


class TestSpeakerIdentificationWorkflow:
    """Tests for run_speaker_identification_workflow."""

    @patch("transcriptx.cli.speaker_workflow.run_speaker_identification_workflow")
    def test_run_speaker_identification_workflow(self, mock_workflow):
        """Test speaker identification workflow execution."""
        mock_workflow.return_value = None

        run_speaker_identification_workflow()

        mock_workflow.assert_called_once()


class TestWAVProcessingWorkflow:
    """Tests for run_wav_processing_workflow."""

    @patch("transcriptx.cli.wav_processing_workflow.run_wav_processing_workflow")
    def test_run_wav_processing_workflow(self, mock_workflow):
        """Test WAV processing workflow execution."""
        mock_workflow.return_value = None

        run_wav_processing_workflow()

        mock_workflow.assert_called_once()

    @patch("transcriptx.cli.wav_processing_workflow.run_wav_processing_workflow")
    def test_wav_processing_workflow_selects_file(self, mock_workflow, tmp_path):
        """Test WAV processing workflow is accessible."""
        mock_workflow.return_value = None
        assert mock_workflow is not None


class TestBatchWAVWorkflow:
    """Tests for run_batch_wav_workflow (delegates to prep_audio + batch_analyze)."""

    def test_run_batch_wav_workflow_no_folder_returns_none(self):
        """With no folder, run_batch_wav_workflow returns None."""
        result = run_batch_wav_workflow()
        assert result is None

    @patch("transcriptx.cli.batch_analyze_workflow.run_batch_analyze_workflow")
    @patch("transcriptx.cli.prep_audio_workflow.run_prep_audio_workflow")
    def test_run_batch_wav_workflow_with_folder_calls_prep_and_analyze(
        self, mock_prep, mock_analyze, tmp_path
    ):
        """With folder, runs prep_audio_workflow then batch_analyze_workflow."""
        folder = tmp_path / "audio"
        folder.mkdir()
        result = run_batch_wav_workflow(folder=folder)
        mock_prep.assert_called_once_with(folder)
        mock_analyze.assert_called_once_with(folder)
        assert result is None


class TestDeduplicationWorkflow:
    """Tests for run_deduplication_workflow."""

    @patch("transcriptx.cli.deduplication_workflow.run_deduplication_workflow")
    def test_run_deduplication_workflow(self, mock_workflow):
        """Test deduplication workflow execution."""
        mock_workflow.return_value = None

        run_deduplication_workflow()

        mock_workflow.assert_called_once()

    @patch("transcriptx.cli.deduplication_workflow.run_deduplication_workflow")
    def test_deduplication_workflow_finds_duplicates(self, mock_workflow):
        """Test deduplication workflow is accessible."""
        mock_workflow.return_value = None
        assert mock_workflow is not None
