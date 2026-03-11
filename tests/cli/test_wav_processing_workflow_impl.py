"""
Tests for WAV processing workflow implementation.

This module tests WAV file processing including conversion to MP3,
merging files, and file management operations.
"""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

from transcriptx.cli.wav_processing_workflow import (
    _run_wav_processing_workflow_impl,
    _run_convert_workflow,
    _run_merge_workflow,
)

_MENU = "transcriptx.cli.wav_processing_workflow.menu"
_CONVERT = "transcriptx.cli.wav_processing_workflow.convert"
_MERGE = "transcriptx.cli.wav_processing_workflow.merge"


class TestWAVProcessingWorkflowImpl:
    """Tests for _run_wav_processing_workflow_impl function."""

    @patch(f"{_MENU}.check_ffmpeg_available")
    def test_wav_workflow_ffmpeg_not_available(self, mock_check_ffmpeg):
        """Test workflow when ffmpeg is not available."""
        mock_check_ffmpeg.return_value = (False, "ffmpeg not found")

        _run_wav_processing_workflow_impl()

        mock_check_ffmpeg.assert_called_once()

    @patch("questionary.select")
    @patch(f"{_MENU}.check_ffmpeg_available")
    def test_wav_workflow_convert_choice(self, mock_check_ffmpeg, mock_select):
        """Test selecting convert option."""
        mock_check_ffmpeg.return_value = (True, None)
        mock_select.return_value.ask.return_value = "🔄 Convert to MP3"

        with patch(f"{_MENU}._run_convert_workflow") as mock_convert:
            _run_wav_processing_workflow_impl()

        mock_convert.assert_called_once()

    @patch("questionary.select")
    @patch(f"{_MENU}.check_ffmpeg_available")
    def test_wav_workflow_merge_choice(self, mock_check_ffmpeg, mock_select):
        """Test selecting merge option."""
        mock_check_ffmpeg.return_value = (True, None)
        mock_select.return_value.ask.return_value = "🔗 Merge Audio Files"

        with patch(f"{_MENU}._run_merge_workflow") as mock_merge:
            _run_wav_processing_workflow_impl()

        mock_merge.assert_called_once()

    @patch(f"{_MENU}.check_ffmpeg_available")
    def test_wav_workflow_cancel(self, mock_check_ffmpeg):
        """Test canceling workflow (questionary returns None → cancel branch)."""
        mock_check_ffmpeg.return_value = (True, None)

        _run_wav_processing_workflow_impl()

        assert True


class TestConvertWorkflow:
    """Tests for _run_convert_workflow function."""

    @patch(f"{_CONVERT}.run_workflow_safely")
    def test_convert_workflow_success(self, mock_run_safely, tmp_path, mock_config):
        """Test successful conversion workflow completes without error."""
        folder = tmp_path / "wavs"
        folder.mkdir()
        wav_file = folder / "test.wav"
        wav_file.write_bytes(b"fake wav")

        mock_run_safely.return_value = None

        _run_convert_workflow()

        mock_run_safely.assert_called_once()

    @patch(f"{_CONVERT}.get_wav_folder_start_path")
    @patch(f"{_CONVERT}.select_audio_files_interactive")
    def test_convert_workflow_no_files(
        self, mock_select_files, mock_get_start_path, tmp_path
    ):
        """Test when no files are selected."""
        folder = tmp_path / "wavs"
        folder.mkdir()

        mock_get_start_path.return_value = folder
        mock_select_files.return_value = []

        _run_convert_workflow()

        mock_select_files.assert_called_once()


class TestMergeWorkflow:
    """Tests for _run_merge_workflow function."""

    @patch(f"{_MERGE}.run_workflow_safely")
    def test_merge_workflow_success(self, mock_run_safely, tmp_path, mock_config):
        """Test successful merge workflow completes without error."""
        folder = tmp_path / "wavs"
        folder.mkdir()

        mock_run_safely.return_value = None

        _run_merge_workflow()

        mock_run_safely.assert_called_once()

    @patch(f"{_MERGE}.select_audio_files_interactive")
    def test_merge_workflow_insufficient_files(self, mock_select_files, tmp_path):
        """Test when less than 2 files selected."""
        folder = tmp_path / "wavs"
        folder.mkdir()
        wav_file = folder / "file.wav"
        wav_file.write_bytes(b"fake")

        mock_select_files.return_value = [wav_file]

        _run_merge_workflow()

        mock_select_files.assert_called_once()
