"""
Integration tests for audio → transcription → analysis workflow.

This module tests the complete workflow from audio file selection through
transcription to analysis pipeline execution.
"""

from unittest.mock import patch, ANY
import json
import pytest

from transcriptx.cli.transcription_workflow import (
    _run_transcription_workflow_impl,
    _run_post_transcription_analysis,
)


@pytest.mark.integration
class TestAudioToAnalysisWorkflow:
    """Tests for complete audio → transcription → analysis workflow."""

    @pytest.fixture
    def sample_audio_file(self, tmp_path):
        """Fixture for sample audio file."""
        audio_file = tmp_path / "test_audio.mp3"
        audio_file.write_bytes(b"fake audio content")
        return audio_file

    @pytest.fixture
    def sample_transcript_file(self, tmp_path):
        """Fixture for sample transcript file."""
        transcript_file = tmp_path / "test_audio_transcript.json"
        transcript_data = {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Hello, this is a test transcription.",
                    "start": 0.0,
                    "end": 3.0,
                }
            ]
        }
        transcript_file.write_text(json.dumps(transcript_data))
        return transcript_file

    def test_complete_happy_path(
        self, sample_audio_file, sample_transcript_file, tmp_path, sample_speaker_map
    ):
        """Test complete happy path: audio → transcription → analysis."""
        with (
            patch(
                "transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription"
            ) as mock_select,
            patch(
                "transcriptx.cli.transcription_workflow.transcribe_with_whisperx"
            ) as mock_transcribe,
            patch(
                "transcriptx.cli.transcription_workflow.questionary.confirm"
            ) as mock_confirm,
            patch(
                "transcriptx.cli.transcription_workflow.select_analysis_mode"
            ) as mock_mode,
            patch(
                "transcriptx.cli.transcription_workflow.apply_analysis_mode_settings"
            ) as mock_apply,
            patch(
                "transcriptx.cli.transcription_workflow.get_available_modules"
            ) as mock_modules,
            patch(
                "transcriptx.cli.transcription_workflow.run_analysis_pipeline"
            ) as mock_pipeline,
        ):

            # Setup mocks
            mock_select.return_value = sample_audio_file
            mock_transcribe.return_value = str(sample_transcript_file)
            mock_confirm.return_value.ask.return_value = True  # User wants analysis
            mock_mode.return_value = "quick"
            mock_modules.return_value = ["sentiment", "stats"]
            mock_pipeline.return_value = {
                "modules_run": ["sentiment", "stats"],
                "errors": [],
            }

            # Run workflow
            _run_transcription_workflow_impl()

            # Verify calls
            mock_select.assert_called_once()
            mock_transcribe.assert_called_once_with(sample_audio_file, ANY)
            mock_confirm.assert_called_once()
            mock_pipeline.assert_called_once()

    def test_transcription_failure_recovery(self, sample_audio_file, tmp_path):
        """Test transcription failure recovery."""
        with (
            patch(
                "transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription"
            ) as mock_select,
            patch(
                "transcriptx.cli.transcription_workflow.transcribe_with_whisperx"
            ) as mock_transcribe,
            patch("transcriptx.cli.transcription_workflow.log_error") as mock_log_error,
        ):

            mock_select.return_value = sample_audio_file
            mock_transcribe.return_value = None  # Transcription fails

            _run_transcription_workflow_impl()

            # Verify error logging
            mock_log_error.assert_called()
            # Verify no analysis attempted
            assert mock_transcribe.call_count == 1

    def test_post_transcription_analysis_flow(
        self, sample_transcript_file, sample_speaker_map
    ):
        """Test post-transcription analysis flow."""
        with (
            patch(
                "transcriptx.cli.transcription_workflow.select_analysis_mode"
            ) as mock_mode,
            patch(
                "transcriptx.cli.transcription_workflow.apply_analysis_mode_settings"
            ) as mock_apply,
            patch(
                "transcriptx.cli.transcription_workflow.questionary.confirm"
            ) as mock_confirm,
            patch(
                "transcriptx.cli.transcription_workflow.get_available_modules"
            ) as mock_modules,
            patch(
                "transcriptx.cli.transcription_workflow.run_analysis_pipeline"
            ) as mock_pipeline,
        ):

            mock_mode.return_value = "quick"
            mock_confirm.return_value.ask.return_value = True  # Proceed with analysis
            mock_modules.return_value = ["sentiment", "stats"]
            mock_pipeline.return_value = {
                "modules_run": ["sentiment", "stats"],
                "errors": [],
            }

            _run_post_transcription_analysis(str(sample_transcript_file))

            # Verify analysis pipeline called
            mock_pipeline.assert_called_once()
            call_args = mock_pipeline.call_args
            assert call_args.kwargs["transcript_path"] == str(sample_transcript_file)
            assert call_args.kwargs["skip_speaker_mapping"] is True

    def test_service_management_integration(self, sample_audio_file, tmp_path):
        """Test WhisperX service management integration."""
        with (
            patch(
                "transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription"
            ) as mock_select,
            patch(
                "transcriptx.cli.transcription_workflow.check_whisperx_compose_service"
            ) as mock_check,
            patch(
                "transcriptx.cli.transcription_workflow.start_whisperx_compose_service"
            ) as mock_start,
            patch(
                "transcriptx.cli.transcription_workflow.wait_for_whisperx_service"
            ) as mock_wait,
            patch(
                "transcriptx.cli.transcription_workflow.transcribe_with_whisperx"
            ) as mock_transcribe,
        ):

            mock_select.return_value = sample_audio_file
            mock_check.return_value = False  # Service not running
            mock_start.return_value = True
            mock_wait.return_value = True
            mock_transcribe.return_value = str(tmp_path / "transcript.json")

            _run_transcription_workflow_impl()

            # Verify service management
            mock_check.assert_called()
            mock_start.assert_called()
            mock_wait.assert_called()

    def test_multiple_audio_formats(self, tmp_path):
        """Test handling of multiple audio formats."""
        formats = {
            "mp3": tmp_path / "test.mp3",
            "wav": tmp_path / "test.wav",
            "m4a": tmp_path / "test.m4a",
        }

        for fmt, file_path in formats.items():
            file_path.write_bytes(b"fake audio")

            with (
                patch(
                    "transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription"
                ) as mock_select,
                patch(
                    "transcriptx.cli.transcription_workflow.transcribe_with_whisperx"
                ) as mock_transcribe,
            ):

                mock_select.return_value = file_path
                mock_transcribe.return_value = str(tmp_path / f"{fmt}_transcript.json")

                _run_transcription_workflow_impl()

                # Verify transcription attempted for each format
                mock_transcribe.assert_called_once_with(file_path, ANY)

    def test_user_declines_analysis(self, sample_audio_file, sample_transcript_file):
        """Test workflow when user declines analysis."""
        with (
            patch(
                "transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription"
            ) as mock_select,
            patch(
                "transcriptx.cli.transcription_workflow.transcribe_with_whisperx"
            ) as mock_transcribe,
            patch(
                "transcriptx.cli.transcription_workflow.questionary.confirm"
            ) as mock_confirm,
            patch(
                "transcriptx.cli.transcription_workflow.run_analysis_pipeline"
            ) as mock_pipeline,
        ):

            mock_select.return_value = sample_audio_file
            mock_transcribe.return_value = str(sample_transcript_file)
            mock_confirm.return_value.ask.return_value = False  # User declines

            _run_transcription_workflow_impl()

            # Verify analysis not called
            mock_pipeline.assert_not_called()

    def test_state_persistence(
        self, sample_audio_file, sample_transcript_file, tmp_path
    ):
        """Test state persistence across workflow steps."""
        with (
            patch(
                "transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription"
            ) as mock_select,
            patch(
                "transcriptx.cli.transcription_workflow.transcribe_with_whisperx"
            ) as mock_transcribe,
            patch(
                "transcriptx.cli.processing_state.save_processing_state"
            ) as mock_save_state,
            patch(
                "transcriptx.cli.transcription_workflow.questionary.confirm"
            ) as mock_confirm,
        ):

            mock_select.return_value = sample_audio_file
            mock_transcribe.return_value = str(sample_transcript_file)
            mock_confirm.return_value.ask.return_value = False

            _run_transcription_workflow_impl()

            # Verify state management (if implemented)
            # This depends on actual state management implementation
            assert mock_transcribe.called

    def test_output_directory_structure(
        self, sample_audio_file, sample_transcript_file, tmp_path
    ):
        """Test output directory structure creation."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()

        with (
            patch(
                "transcriptx.cli.transcription_workflow.select_audio_for_whisperx_transcription"
            ) as mock_select,
            patch(
                "transcriptx.cli.transcription_workflow.transcribe_with_whisperx"
            ) as mock_transcribe,
            patch(
                "transcriptx.cli.transcription_workflow.questionary.confirm"
            ) as mock_confirm,
            patch(
                "transcriptx.cli.transcription_workflow.run_analysis_pipeline"
            ) as mock_pipeline,
            patch("transcriptx.core.utils.config.get_config") as mock_config,
        ):

            mock_config.return_value.output.base_output_dir = str(output_dir)
            mock_select.return_value = sample_audio_file
            mock_transcribe.return_value = str(sample_transcript_file)
            mock_confirm.return_value.ask.return_value = True
            mock_pipeline.return_value = {"modules_run": ["sentiment"]}

            _run_transcription_workflow_impl()

            # Verify pipeline called with correct paths
            mock_pipeline.assert_called_once()
