"""
Tests for analysis workflow implementation.

This module tests the actual _run_analysis_workflow_impl(skip_speaker_gate=True) function with
real flows including file selection, module selection, analysis execution,
and post-analysis menu interactions.
"""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

from transcriptx.cli.analysis_workflow import (
    _run_analysis_workflow_impl,
    _show_post_analysis_menu,
)


class TestAnalysisWorkflowImpl:
    """Tests for _run_analysis_workflow_impl function."""

    @patch("transcriptx.cli.analysis_workflow.select_analysis_target_interactive")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_mode")
    @patch("transcriptx.cli.analysis_workflow.apply_analysis_mode_settings")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_modules")
    @patch("transcriptx.cli.analysis_workflow.filter_modules_by_mode")
    @patch("transcriptx.cli.analysis_workflow.questionary.confirm")
    @patch("transcriptx.cli.analysis_workflow.run_analysis_pipeline")
    @patch("transcriptx.cli.analysis_workflow._show_post_analysis_menu")
    def test_analysis_workflow_complete_flow(
        self,
        mock_menu,
        mock_pipeline,
        mock_confirm,
        mock_filter,
        mock_select_modules,
        mock_apply_settings,
        mock_select_mode,
        mock_select_file,
        temp_transcript_file,
    ):
        """Test complete analysis workflow flow."""
        mock_selection = MagicMock()
        mock_selection.kind = "paths"
        mock_selection.paths = [temp_transcript_file]
        mock_select_file.return_value = mock_selection
        mock_select_mode.return_value = "quick"
        mock_select_modules.return_value = (["sentiment", "stats"], "manual")
        mock_filter.return_value = ["sentiment", "stats"]
        mock_confirm.return_value.ask.return_value = True
        mock_pipeline.return_value = {
            "modules_run": ["sentiment", "stats"],
            "errors": [],
        }

        _run_analysis_workflow_impl(skip_speaker_gate=True)

        mock_select_file.assert_called_once()
        mock_select_mode.assert_called_once()
        mock_apply_settings.assert_called_once_with("quick")
        mock_select_modules.assert_called_once()
        mock_filter.assert_called_once_with(["sentiment", "stats"], "quick")
        mock_pipeline.assert_called_once()
        mock_menu.assert_called_once()

    @patch("transcriptx.cli.analysis_workflow.select_analysis_target_interactive")
    def test_analysis_workflow_no_file_selected(self, mock_select_file):
        """Test workflow when no file is selected."""
        mock_select_file.return_value = None

        _run_analysis_workflow_impl(skip_speaker_gate=True)

        # Should return early without errors
        mock_select_file.assert_called_once()

    @patch("transcriptx.cli.analysis_workflow.select_analysis_target_interactive")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_mode")
    @patch("transcriptx.cli.analysis_workflow.apply_analysis_mode_settings")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_modules")
    @patch("transcriptx.cli.analysis_workflow.filter_modules_by_mode")
    @patch("transcriptx.cli.analysis_workflow.questionary.confirm")
    def test_analysis_workflow_user_cancels(
        self,
        mock_confirm,
        mock_filter,
        mock_select_modules,
        mock_apply_settings,
        mock_select_mode,
        mock_select_file,
        temp_transcript_file,
    ):
        """Test workflow when user cancels analysis."""
        mock_selection = MagicMock()
        mock_selection.kind = "paths"
        mock_selection.paths = [temp_transcript_file]
        mock_select_file.return_value = mock_selection
        mock_select_mode.return_value = "quick"
        mock_select_modules.return_value = (["sentiment"], "manual")
        mock_filter.return_value = ["sentiment"]
        mock_confirm.return_value.ask.return_value = False

        _run_analysis_workflow_impl(skip_speaker_gate=True)

        mock_confirm.assert_called_once()

    @patch("transcriptx.cli.analysis_workflow.select_analysis_target_interactive")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_mode")
    @patch("transcriptx.cli.analysis_workflow.apply_analysis_mode_settings")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_modules")
    @patch("transcriptx.cli.analysis_workflow.filter_modules_by_mode")
    @patch("transcriptx.cli.analysis_workflow.questionary.confirm")
    @patch("transcriptx.cli.analysis_workflow.run_analysis_pipeline")
    def test_analysis_workflow_with_errors(
        self,
        mock_pipeline,
        mock_confirm,
        mock_filter,
        mock_select_modules,
        mock_apply_settings,
        mock_select_mode,
        mock_select_file,
        temp_transcript_file,
    ):
        """Test workflow when analysis has errors."""
        mock_selection = MagicMock()
        mock_selection.kind = "paths"
        mock_selection.paths = [temp_transcript_file]
        mock_select_file.return_value = mock_selection
        mock_select_mode.return_value = "full"
        mock_select_modules.return_value = (["sentiment", "stats"], "manual")
        mock_filter.return_value = ["sentiment", "stats"]
        mock_confirm.return_value.ask.return_value = True
        mock_pipeline.return_value = {
            "modules_run": ["sentiment"],
            "errors": ["Error in stats module"],
        }

        with patch("transcriptx.cli.analysis_workflow._show_post_analysis_menu"):
            _run_analysis_workflow_impl(skip_speaker_gate=True)

        mock_pipeline.assert_called_once()

    @patch("transcriptx.cli.analysis_workflow.select_analysis_target_interactive")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_mode")
    @patch("transcriptx.cli.analysis_workflow.apply_analysis_mode_settings")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_modules")
    @patch("transcriptx.cli.analysis_workflow.filter_modules_by_mode")
    @patch("transcriptx.cli.analysis_workflow.questionary.confirm")
    @patch("transcriptx.cli.analysis_workflow.run_analysis_pipeline")
    def test_analysis_workflow_pipeline_exception(
        self,
        mock_pipeline,
        mock_confirm,
        mock_filter,
        mock_select_modules,
        mock_apply_settings,
        mock_select_mode,
        mock_select_file,
        temp_transcript_file,
    ):
        """Test workflow when pipeline raises exception."""
        mock_selection = MagicMock()
        mock_selection.kind = "paths"
        mock_selection.paths = [temp_transcript_file]
        mock_select_file.return_value = mock_selection
        mock_select_mode.return_value = "quick"
        mock_select_modules.return_value = (["sentiment"], "manual")
        mock_filter.return_value = ["sentiment"]
        mock_confirm.return_value.ask.return_value = True
        mock_pipeline.side_effect = Exception("Pipeline error")

        with patch("transcriptx.cli.analysis_workflow.log_error") as mock_log_error:
            _run_analysis_workflow_impl(skip_speaker_gate=True)

        mock_log_error.assert_called_once()
        mock_pipeline.assert_called_once()


class TestPostAnalysisMenu:
    """Tests for _show_post_analysis_menu function."""

    @patch("transcriptx.cli.analysis_workflow.questionary.select")
    @patch("transcriptx.cli.analysis_workflow.subprocess.run")
    def test_post_analysis_menu_open_outputs(
        self, mock_subprocess, mock_select, temp_transcript_file
    ):
        """Test opening outputs folder from post-analysis menu."""
        mock_select.return_value.ask.side_effect = [
            "📂 Open outputs folder",
            "🏠 Return to main menu",
        ]

        results = {"modules_run": ["sentiment"], "errors": []}

        _show_post_analysis_menu(temp_transcript_file, results)

        assert mock_select.called
        assert mock_subprocess.called

    @patch("transcriptx.cli.analysis_workflow.questionary.select")
    def test_post_analysis_menu_return_to_main(self, mock_select, temp_transcript_file):
        """Test returning to main menu from post-analysis menu."""
        mock_select.return_value.ask.return_value = "🏠 Return to main menu"

        results = {"modules_run": ["sentiment"], "errors": []}

        _show_post_analysis_menu(temp_transcript_file, results)

        assert mock_select.called


class TestAnalysisWorkflowErrorHandling:
    """Tests for error handling in analysis workflow."""

    @patch("transcriptx.cli.analysis_workflow.apply_analysis_mode_settings")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_target_interactive")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_mode")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_modules")
    @patch("transcriptx.cli.analysis_workflow.run_analysis_pipeline")
    def test_invalid_transcript_file_corrupted_json(
        self, mock_pipeline, mock_select_modules, mock_select_mode, mock_select,
        mock_apply_settings, tmp_path
    ):
        """Test handling when pipeline raises ValueError for corrupted transcript."""
        corrupted_file = tmp_path / "corrupted.json"
        corrupted_file.write_text('{"segments": []}')

        mock_selection = MagicMock()
        mock_selection.kind = "paths"
        mock_selection.paths = [corrupted_file]
        mock_select.return_value = mock_selection
        mock_select_mode.return_value = "quick"
        mock_select_modules.return_value = (["sentiment"], "manual")
        mock_pipeline.side_effect = ValueError("Invalid JSON structure")

        with (
            patch("transcriptx.cli.analysis_workflow.filter_modules_by_mode") as mock_filter,
            patch("transcriptx.cli.analysis_workflow.questionary.confirm") as mock_confirm,
            patch("transcriptx.cli.analysis_workflow.log_error") as mock_log_error,
        ):
            mock_filter.return_value = ["sentiment"]
            mock_confirm.return_value.ask.return_value = True
            _run_analysis_workflow_impl(skip_speaker_gate=True)

        mock_log_error.assert_called()

    @patch("transcriptx.cli.analysis_workflow.apply_analysis_mode_settings")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_target_interactive")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_mode")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_modules")
    @patch("transcriptx.cli.analysis_workflow.run_analysis_pipeline")
    def test_invalid_transcript_file_missing_fields(
        self, mock_pipeline, mock_select_modules, mock_select_mode, mock_select,
        mock_apply_settings, tmp_path
    ):
        """Test handling when pipeline raises ValueError for missing required fields."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text('{"segments": []}')

        mock_selection = MagicMock()
        mock_selection.kind = "paths"
        mock_selection.paths = [invalid_file]
        mock_select.return_value = mock_selection
        mock_select_mode.return_value = "quick"
        mock_select_modules.return_value = (["sentiment"], "manual")
        mock_pipeline.side_effect = ValueError("Missing required field: segments")

        with (
            patch("transcriptx.cli.analysis_workflow.filter_modules_by_mode") as mock_filter,
            patch("transcriptx.cli.analysis_workflow.questionary.confirm") as mock_confirm,
            patch("transcriptx.cli.analysis_workflow.log_error"),
        ):
            mock_filter.return_value = ["sentiment"]
            mock_confirm.return_value.ask.return_value = True
            _run_analysis_workflow_impl(skip_speaker_gate=True)

        mock_pipeline.assert_called_once()

    @patch("transcriptx.cli.analysis_workflow.select_analysis_target_interactive")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_mode")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_modules")
    @patch("transcriptx.cli.analysis_workflow.run_analysis_pipeline")
    def test_module_execution_failure(
        self,
        mock_pipeline,
        mock_select_modules,
        mock_select_mode,
        mock_select_file,
        temp_transcript_file,
    ):
        """Test handling when module fails to load."""
        mock_selection = MagicMock()
        mock_selection.kind = "paths"
        mock_selection.paths = [temp_transcript_file]
        mock_select_file.return_value = mock_selection
        mock_select_mode.return_value = "quick"
        mock_select_modules.return_value = (["sentiment", "invalid_module"], "manual")
        mock_pipeline.return_value = {
            "modules_run": ["sentiment"],
            "errors": ["Module 'invalid_module' failed to load"],
        }

        with (
            patch("transcriptx.cli.analysis_workflow.questionary.confirm") as mock_confirm,
            patch("transcriptx.cli.analysis_workflow.filter_modules_by_mode") as mock_filter,
            patch("transcriptx.cli.analysis_workflow._show_post_analysis_menu"),
        ):
            mock_confirm.return_value.ask.return_value = True
            mock_filter.return_value = ["sentiment", "invalid_module"]

            _run_analysis_workflow_impl(skip_speaker_gate=True)

        mock_pipeline.assert_called_once()
        result = mock_pipeline.return_value
        assert "errors" in result

    @patch("transcriptx.cli.analysis_workflow.select_analysis_target_interactive")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_mode")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_modules")
    @patch("transcriptx.cli.analysis_workflow.run_analysis_pipeline")
    def test_module_timeout_handling(
        self,
        mock_pipeline,
        mock_select_modules,
        mock_select_mode,
        mock_select_file,
        temp_transcript_file,
    ):
        """Test handling when module times out."""
        mock_selection = MagicMock()
        mock_selection.kind = "paths"
        mock_selection.paths = [temp_transcript_file]
        mock_select_file.return_value = mock_selection
        mock_select_mode.return_value = "quick"
        mock_select_modules.return_value = (["sentiment", "stats"], "manual")
        mock_pipeline.return_value = {
            "modules_run": ["sentiment"],
            "errors": ["Module 'stats' timed out after 600 seconds"],
        }

        with (
            patch("transcriptx.cli.analysis_workflow.questionary.confirm") as mock_confirm,
            patch("transcriptx.cli.analysis_workflow.filter_modules_by_mode") as mock_filter,
            patch("transcriptx.cli.analysis_workflow._show_post_analysis_menu"),
        ):
            mock_confirm.return_value.ask.return_value = True
            mock_filter.return_value = ["sentiment", "stats"]

            _run_analysis_workflow_impl(skip_speaker_gate=True)

        mock_pipeline.assert_called_once()

    @pytest.mark.slow
    @patch("transcriptx.cli.analysis_workflow.select_analysis_target_interactive")
    @patch("transcriptx.cli.analysis_workflow.run_analysis_pipeline")
    def test_output_generation_failure_disk_full(
        self, mock_pipeline, mock_select_file, temp_transcript_file, tmp_path
    ):
        """Test handling when disk is full during output generation."""
        mock_selection = MagicMock()
        mock_selection.kind = "paths"
        mock_selection.paths = [temp_transcript_file]
        mock_select_file.return_value = mock_selection
        mock_pipeline.side_effect = OSError("No space left on device")

        with (
            patch("transcriptx.cli.analysis_workflow.select_analysis_mode") as mock_mode,
            patch("transcriptx.cli.analysis_workflow.select_analysis_modules") as mock_modules,
            patch("transcriptx.cli.analysis_workflow.questionary.confirm") as mock_confirm,
            patch("transcriptx.cli.analysis_workflow.filter_modules_by_mode") as mock_filter,
            patch("transcriptx.cli.analysis_workflow.log_error") as mock_log_error,
        ):
            mock_mode.return_value = "quick"
            mock_modules.return_value = (["sentiment"], "manual")
            mock_filter.return_value = ["sentiment"]
            mock_confirm.return_value.ask.return_value = True

            _run_analysis_workflow_impl(skip_speaker_gate=True)

        mock_log_error.assert_called()

    @patch("transcriptx.cli.analysis_workflow.select_analysis_target_interactive")
    @patch("transcriptx.cli.analysis_workflow.run_analysis_pipeline")
    def test_output_generation_failure_permission_denied(
        self, mock_pipeline, mock_select_file, temp_transcript_file
    ):
        """Test handling when output directory is not writable."""
        mock_selection = MagicMock()
        mock_selection.kind = "paths"
        mock_selection.paths = [temp_transcript_file]
        mock_select_file.return_value = mock_selection
        mock_pipeline.side_effect = PermissionError("Permission denied")

        with (
            patch("transcriptx.cli.analysis_workflow.select_analysis_mode") as mock_mode,
            patch("transcriptx.cli.analysis_workflow.select_analysis_modules") as mock_modules,
            patch("transcriptx.cli.analysis_workflow.questionary.confirm") as mock_confirm,
            patch("transcriptx.cli.analysis_workflow.filter_modules_by_mode") as mock_filter,
            patch("transcriptx.cli.analysis_workflow.log_error") as mock_log_error,
        ):
            mock_mode.return_value = "quick"
            mock_modules.return_value = (["sentiment"], "manual")
            mock_filter.return_value = ["sentiment"]
            mock_confirm.return_value.ask.return_value = True

            _run_analysis_workflow_impl(skip_speaker_gate=True)

        mock_log_error.assert_called()

    @patch("transcriptx.cli.analysis_workflow.select_analysis_target_interactive")
    @patch("transcriptx.cli.analysis_workflow.run_analysis_pipeline")
    def test_network_api_error_geocoding(
        self, mock_pipeline, mock_select_file, temp_transcript_file
    ):
        """Test handling when geocoding API fails."""
        mock_selection = MagicMock()
        mock_selection.kind = "paths"
        mock_selection.paths = [temp_transcript_file]
        mock_select_file.return_value = mock_selection
        mock_pipeline.return_value = {
            "modules_run": ["sentiment", "ner"],
            "errors": ["Geocoding API unavailable, continuing without geocoding"],
        }

        with (
            patch("transcriptx.cli.analysis_workflow.select_analysis_mode") as mock_mode,
            patch("transcriptx.cli.analysis_workflow.apply_analysis_mode_settings"),
            patch("transcriptx.cli.analysis_workflow.select_analysis_modules") as mock_modules,
            patch("transcriptx.cli.analysis_workflow.questionary.confirm") as mock_confirm,
            patch("transcriptx.cli.analysis_workflow.filter_modules_by_mode") as mock_filter,
            patch("transcriptx.cli.analysis_workflow._show_post_analysis_menu"),
        ):
            mock_mode.return_value = "full"
            mock_modules.return_value = (["sentiment", "ner"], "manual")
            mock_filter.return_value = ["sentiment", "ner"]
            mock_confirm.return_value.ask.return_value = True

            _run_analysis_workflow_impl(skip_speaker_gate=True)

        mock_pipeline.assert_called_once()
        result = mock_pipeline.return_value
        assert "ner" in result["modules_run"]

    @patch("transcriptx.cli.analysis_workflow.select_analysis_target_interactive")
    @patch("transcriptx.cli.analysis_workflow.run_analysis_pipeline")
    def test_resource_exhaustion_memory(
        self, mock_pipeline, mock_select_file, temp_transcript_file
    ):
        """Test handling when memory limit is reached."""
        mock_selection = MagicMock()
        mock_selection.kind = "paths"
        mock_selection.paths = [temp_transcript_file]
        mock_select_file.return_value = mock_selection
        mock_pipeline.side_effect = MemoryError("Memory limit exceeded")

        with (
            patch("transcriptx.cli.analysis_workflow.select_analysis_mode") as mock_mode,
            patch("transcriptx.cli.analysis_workflow.apply_analysis_mode_settings"),
            patch("transcriptx.cli.analysis_workflow.select_analysis_modules") as mock_modules,
            patch("transcriptx.cli.analysis_workflow.questionary.confirm") as mock_confirm,
            patch("transcriptx.cli.analysis_workflow.filter_modules_by_mode") as mock_filter,
            patch("transcriptx.cli.analysis_workflow.log_error") as mock_log_error,
        ):
            mock_mode.return_value = "full"
            mock_modules.return_value = (["sentiment"], "manual")
            mock_filter.return_value = ["sentiment"]
            mock_confirm.return_value.ask.return_value = True

            _run_analysis_workflow_impl(skip_speaker_gate=True)

        mock_log_error.assert_called()

    @patch("transcriptx.cli.analysis_workflow.apply_analysis_mode_settings")
    @patch("transcriptx.cli.analysis_workflow.select_analysis_target_interactive")
    @patch("transcriptx.cli.analysis_workflow.run_analysis_pipeline")
    def test_wrong_file_format(self, mock_pipeline, mock_select, mock_apply, tmp_path):
        """Test handling when pipeline raises for wrong file format."""
        wrong_file = tmp_path / "test.json"
        wrong_file.write_text('{"segments": []}')

        mock_selection = MagicMock()
        mock_selection.kind = "paths"
        mock_selection.paths = [wrong_file]
        mock_select.return_value = mock_selection
        mock_pipeline.side_effect = ValueError("Invalid file format")

        with (
            patch("transcriptx.cli.analysis_workflow.select_analysis_mode") as mock_mode,
            patch("transcriptx.cli.analysis_workflow.select_analysis_modules") as mock_modules,
            patch("transcriptx.cli.analysis_workflow.questionary.confirm") as mock_confirm,
            patch("transcriptx.cli.analysis_workflow.filter_modules_by_mode") as mock_filter,
            patch("transcriptx.cli.analysis_workflow.log_error") as mock_log_error,
        ):
            mock_mode.return_value = "quick"
            mock_modules.return_value = (["sentiment"], "manual")
            mock_filter.return_value = ["sentiment"]
            mock_confirm.return_value.ask.return_value = True

            _run_analysis_workflow_impl(skip_speaker_gate=True)

        mock_log_error.assert_called()
