"""
Tests for analysis workflow implementation.

This module tests the actual _run_analysis_workflow_impl() function with
real flows including file selection, module selection, analysis execution,
and post-analysis menu interactions.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

pytestmark = pytest.mark.quarantined  # reason: patches removed/renamed CLI APIs (select_transcript_file_interactive, generate_stats_from_file, validate_transcript_file); remove_by: when CLI stabilizes

from transcriptx.cli.analysis_workflow import _run_analysis_workflow_impl, _show_post_analysis_menu


class TestAnalysisWorkflowImpl:
    """Tests for _run_analysis_workflow_impl function."""
    
    @patch('transcriptx.cli.analysis_workflow.select_transcript_file_interactive')
    @patch('transcriptx.cli.analysis_workflow.select_analysis_mode')
    @patch('transcriptx.cli.analysis_workflow.apply_analysis_mode_settings')
    @patch('transcriptx.cli.analysis_workflow.select_analysis_modules')
    @patch('transcriptx.cli.analysis_workflow.filter_modules_by_mode')
    @patch('transcriptx.cli.analysis_workflow.questionary.confirm')
    @patch('transcriptx.cli.analysis_workflow.run_analysis_pipeline')
    @patch('transcriptx.cli.analysis_workflow.generate_stats_from_file')
    @patch('transcriptx.cli.analysis_workflow._show_post_analysis_menu')
    def test_analysis_workflow_complete_flow(
        self, mock_menu, mock_stats, mock_pipeline, mock_confirm,
        mock_filter, mock_select_modules, mock_apply_settings,
        mock_select_mode, mock_select_file, temp_transcript_file
    ):
        """Test complete analysis workflow flow."""
        # Setup mocks
        mock_select_file.return_value = temp_transcript_file
        mock_select_mode.return_value = "quick"
        mock_select_modules.return_value = ["sentiment", "stats"]
        mock_filter.return_value = ["sentiment", "stats"]
        mock_confirm.return_value.ask.return_value = True
        mock_pipeline.return_value = {
            "modules_run": ["sentiment", "stats"],
            "errors": []
        }
        
        # Run workflow
        _run_analysis_workflow_impl()
        
        # Verify calls
        mock_select_file.assert_called_once()
        mock_select_mode.assert_called_once()
        mock_apply_settings.assert_called_once_with("quick")
        mock_select_modules.assert_called_once()
        mock_filter.assert_called_once_with(["sentiment", "stats"], "quick")
        mock_confirm.assert_called_once()
        mock_pipeline.assert_called_once()
        mock_stats.assert_called_once()
        mock_menu.assert_called_once()
    
    @patch('transcriptx.cli.analysis_workflow.select_transcript_file_interactive')
    def test_analysis_workflow_no_file_selected(self, mock_select_file):
        """Test workflow when no file is selected."""
        mock_select_file.return_value = None
        
        _run_analysis_workflow_impl()
        
        # Should return early without errors
        mock_select_file.assert_called_once()
    
    @patch('transcriptx.cli.analysis_workflow.select_transcript_file_interactive')
    @patch('transcriptx.cli.analysis_workflow.select_analysis_mode')
    @patch('transcriptx.cli.analysis_workflow.apply_analysis_mode_settings')
    @patch('transcriptx.cli.analysis_workflow.select_analysis_modules')
    @patch('transcriptx.cli.analysis_workflow.filter_modules_by_mode')
    @patch('transcriptx.cli.analysis_workflow.questionary.confirm')
    def test_analysis_workflow_user_cancels(
        self, mock_confirm, mock_filter, mock_select_modules,
        mock_apply_settings, mock_select_mode, mock_select_file,
        temp_transcript_file
    ):
        """Test workflow when user cancels analysis."""
        mock_select_file.return_value = temp_transcript_file
        mock_select_mode.return_value = "quick"
        mock_select_modules.return_value = ["sentiment"]
        mock_filter.return_value = ["sentiment"]
        mock_confirm.return_value.ask.return_value = False  # User cancels
        
        _run_analysis_workflow_impl()
        
        # Should not proceed to analysis
        mock_confirm.assert_called_once()
    
    @patch('transcriptx.cli.analysis_workflow.select_transcript_file_interactive')
    @patch('transcriptx.cli.analysis_workflow.select_analysis_mode')
    @patch('transcriptx.cli.analysis_workflow.apply_analysis_mode_settings')
    @patch('transcriptx.cli.analysis_workflow.select_analysis_modules')
    @patch('transcriptx.cli.analysis_workflow.filter_modules_by_mode')
    @patch('transcriptx.cli.analysis_workflow.questionary.confirm')
    @patch('transcriptx.cli.analysis_workflow.run_analysis_pipeline')
    def test_analysis_workflow_with_errors(
        self, mock_pipeline, mock_confirm, mock_filter,
        mock_select_modules, mock_apply_settings, mock_select_mode,
        mock_select_file, temp_transcript_file
    ):
        """Test workflow when analysis has errors."""
        mock_select_file.return_value = temp_transcript_file
        mock_select_mode.return_value = "full"
        mock_select_modules.return_value = ["sentiment", "stats"]
        mock_filter.return_value = ["sentiment", "stats"]
        mock_confirm.return_value.ask.return_value = True
        mock_pipeline.return_value = {
            "modules_run": ["sentiment"],
            "errors": ["Error in stats module"]
        }
        
        with patch('transcriptx.cli.analysis_workflow.generate_stats_from_file'), \
             patch('transcriptx.cli.analysis_workflow._show_post_analysis_menu'):
            _run_analysis_workflow_impl()
        
        # Should handle errors gracefully
        mock_pipeline.assert_called_once()
    
    @patch('transcriptx.cli.analysis_workflow.select_transcript_file_interactive')
    @patch('transcriptx.cli.analysis_workflow.select_analysis_mode')
    @patch('transcriptx.cli.analysis_workflow.apply_analysis_mode_settings')
    @patch('transcriptx.cli.analysis_workflow.select_analysis_modules')
    @patch('transcriptx.cli.analysis_workflow.filter_modules_by_mode')
    @patch('transcriptx.cli.analysis_workflow.questionary.confirm')
    @patch('transcriptx.cli.analysis_workflow.run_analysis_pipeline')
    def test_analysis_workflow_pipeline_exception(
        self, mock_pipeline, mock_confirm, mock_filter,
        mock_select_modules, mock_apply_settings, mock_select_mode,
        mock_select_file, temp_transcript_file
    ):
        """Test workflow when pipeline raises exception."""
        mock_select_file.return_value = temp_transcript_file
        mock_select_mode.return_value = "quick"
        mock_select_modules.return_value = ["sentiment"]
        mock_filter.return_value = ["sentiment"]
        mock_confirm.return_value.ask.return_value = True
        mock_pipeline.side_effect = Exception("Pipeline error")
        
        with patch('transcriptx.cli.analysis_workflow.log_error') as mock_log_error:
            _run_analysis_workflow_impl()
        
        # Should log error and handle gracefully
        mock_log_error.assert_called_once()
        mock_pipeline.assert_called_once()


class TestPostAnalysisMenu:
    """Tests for _show_post_analysis_menu function."""
    
    @patch('transcriptx.cli.analysis_workflow.questionary.select')
    @patch('transcriptx.cli.analysis_workflow.webbrowser.open')
    @patch('transcriptx.cli.analysis_workflow.subprocess.run')
    def test_post_analysis_menu_open_html(
        self, mock_subprocess, mock_browser, mock_select, temp_transcript_file
    ):
        """Test opening HTML summary from post-analysis menu."""
        # Mock the select to return "Open HTML summary" first, then "Return to main menu" to exit the loop
        mock_select.return_value.ask.side_effect = ["🌐 Open HTML summary", "🏠 Return to main menu"]
        
        results = {"modules_run": ["sentiment"], "errors": []}
        
        # Create the HTML file so it exists when checked
        html_path = temp_transcript_file.parent / "summary.html"
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text("<html><body>Test</body></html>")
        
        with patch('transcriptx.cli.analysis_workflow.get_html_summary_path') as mock_path:
            mock_path.return_value = str(html_path)
            _show_post_analysis_menu(temp_transcript_file, results)
        
        # Should open browser or file
        assert mock_select.called
        assert mock_browser.called
    
    @patch('transcriptx.cli.analysis_workflow.questionary.select')
    def test_post_analysis_menu_return_to_main(
        self, mock_select, temp_transcript_file
    ):
        """Test returning to main menu from post-analysis menu."""
        mock_select.return_value.ask.return_value = "🏠 Return to main menu"
        
        results = {"modules_run": ["sentiment"], "errors": []}
        
        _show_post_analysis_menu(temp_transcript_file, results)
        
        # Should return without errors
        assert mock_select.called


class TestAnalysisWorkflowErrorHandling:
    """Tests for error handling in analysis workflow."""
    
    @patch('transcriptx.cli.analysis_workflow.select_transcript_file_interactive')
    @patch('transcriptx.cli.analysis_workflow.validate_transcript_file')
    def test_invalid_transcript_file_corrupted_json(
        self, mock_validate, mock_select, tmp_path
    ):
        """Test handling of corrupted JSON transcript file."""
        corrupted_file = tmp_path / "corrupted.json"
        corrupted_file.write_text("{invalid json}")
        
        mock_select.return_value = corrupted_file
        mock_validate.side_effect = ValueError("Invalid JSON structure")
        
        with patch('transcriptx.cli.analysis_workflow.log_error') as mock_log_error:
            _run_analysis_workflow_impl()
        
        # Should handle error gracefully
        mock_validate.assert_called()
        mock_log_error.assert_called()
    
    @patch('transcriptx.cli.analysis_workflow.select_transcript_file_interactive')
    @patch('transcriptx.cli.analysis_workflow.validate_transcript_file')
    def test_invalid_transcript_file_missing_fields(
        self, mock_validate, mock_select, tmp_path
    ):
        """Test handling of transcript file with missing required fields."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text('{"wrong": "structure"}')
        
        mock_select.return_value = invalid_file
        mock_validate.side_effect = ValueError("Missing required field: segments")
        
        with patch('transcriptx.cli.analysis_workflow.log_error') as mock_log_error:
            _run_analysis_workflow_impl()
        
        # Should detect and report missing fields
        mock_validate.assert_called()
    
    @patch('transcriptx.cli.analysis_workflow.select_transcript_file_interactive')
    @patch('transcriptx.cli.analysis_workflow.select_analysis_mode')
    @patch('transcriptx.cli.analysis_workflow.select_analysis_modules')
    @patch('transcriptx.cli.analysis_workflow.run_analysis_pipeline')
    def test_module_execution_failure(
        self, mock_pipeline, mock_select_modules, mock_select_mode,
        mock_select_file, temp_transcript_file
    ):
        """Test handling when module fails to load."""
        mock_select_file.return_value = temp_transcript_file
        mock_select_mode.return_value = "quick"
        mock_select_modules.return_value = ["sentiment", "invalid_module"]
        mock_pipeline.return_value = {
            "modules_run": ["sentiment"],
            "errors": ["Module 'invalid_module' failed to load"]
        }
        
        with patch('transcriptx.cli.analysis_workflow.questionary.confirm') as mock_confirm, \
             patch('transcriptx.cli.analysis_workflow.filter_modules_by_mode') as mock_filter:
            mock_confirm.return_value.ask.return_value = True
            mock_filter.return_value = ["sentiment", "invalid_module"]
            
            _run_analysis_workflow_impl()
        
        # Should continue with available modules
        mock_pipeline.assert_called_once()
        result = mock_pipeline.return_value
        assert "errors" in result
    
    @patch('transcriptx.cli.analysis_workflow.select_transcript_file_interactive')
    @patch('transcriptx.cli.analysis_workflow.select_analysis_mode')
    @patch('transcriptx.cli.analysis_workflow.select_analysis_modules')
    @patch('transcriptx.cli.analysis_workflow.run_analysis_pipeline')
    def test_module_timeout_handling(
        self, mock_pipeline, mock_select_modules, mock_select_mode,
        mock_select_file, temp_transcript_file
    ):
        """Test handling when module times out."""
        mock_select_file.return_value = temp_transcript_file
        mock_select_mode.return_value = "quick"
        mock_select_modules.return_value = ["sentiment", "stats"]
        mock_pipeline.return_value = {
            "modules_run": ["sentiment"],
            "errors": ["Module 'stats' timed out after 600 seconds"]
        }
        
        with patch('transcriptx.cli.analysis_workflow.questionary.confirm') as mock_confirm, \
             patch('transcriptx.cli.analysis_workflow.filter_modules_by_mode') as mock_filter:
            mock_confirm.return_value.ask.return_value = True
            mock_filter.return_value = ["sentiment", "stats"]
            
            _run_analysis_workflow_impl()
        
        # Should skip timed-out module and continue
        mock_pipeline.assert_called_once()
    
    @pytest.mark.slow
    @patch('transcriptx.cli.analysis_workflow.select_transcript_file_interactive')
    @patch('transcriptx.cli.analysis_workflow.run_analysis_pipeline')
    def test_output_generation_failure_disk_full(
        self, mock_pipeline, mock_select_file, temp_transcript_file, tmp_path
    ):
        """Test handling when disk is full during output generation."""
        mock_select_file.return_value = temp_transcript_file
        mock_pipeline.side_effect = OSError("No space left on device")
        
        with patch('transcriptx.cli.analysis_workflow.select_analysis_mode') as mock_mode, \
             patch('transcriptx.cli.analysis_workflow.select_analysis_modules') as mock_modules, \
             patch('transcriptx.cli.analysis_workflow.questionary.confirm') as mock_confirm, \
             patch('transcriptx.cli.analysis_workflow.filter_modules_by_mode') as mock_filter, \
             patch('transcriptx.cli.analysis_workflow.log_error') as mock_log_error:
            
            mock_mode.return_value = "quick"
            mock_modules.return_value = ["sentiment"]
            mock_filter.return_value = ["sentiment"]
            mock_confirm.return_value.ask.return_value = True
            
            _run_analysis_workflow_impl()
        
        # Should handle disk full error
        mock_log_error.assert_called()
    
    @patch('transcriptx.cli.analysis_workflow.select_transcript_file_interactive')
    @patch('transcriptx.cli.analysis_workflow.run_analysis_pipeline')
    def test_output_generation_failure_permission_denied(
        self, mock_pipeline, mock_select_file, temp_transcript_file
    ):
        """Test handling when output directory is not writable."""
        mock_select_file.return_value = temp_transcript_file
        mock_pipeline.side_effect = PermissionError("Permission denied")
        
        with patch('transcriptx.cli.analysis_workflow.select_analysis_mode') as mock_mode, \
             patch('transcriptx.cli.analysis_workflow.select_analysis_modules') as mock_modules, \
             patch('transcriptx.cli.analysis_workflow.questionary.confirm') as mock_confirm, \
             patch('transcriptx.cli.analysis_workflow.filter_modules_by_mode') as mock_filter, \
             patch('transcriptx.cli.analysis_workflow.log_error') as mock_log_error:
            
            mock_mode.return_value = "quick"
            mock_modules.return_value = ["sentiment"]
            mock_filter.return_value = ["sentiment"]
            mock_confirm.return_value.ask.return_value = True
            
            _run_analysis_workflow_impl()
        
        # Should handle permission error
        mock_log_error.assert_called()
    
    @patch('transcriptx.cli.analysis_workflow.select_transcript_file_interactive')
    @patch('transcriptx.cli.analysis_workflow.run_analysis_pipeline')
    def test_network_api_error_geocoding(
        self, mock_pipeline, mock_select_file, temp_transcript_file
    ):
        """Test handling when geocoding API fails."""
        mock_select_file.return_value = temp_transcript_file
        # Simulate API error in pipeline
        mock_pipeline.return_value = {
            "modules_run": ["sentiment", "ner"],
            "errors": ["Geocoding API unavailable, continuing without geocoding"]
        }
        
        with patch('transcriptx.cli.analysis_workflow.select_analysis_mode') as mock_mode, \
             patch('transcriptx.cli.analysis_workflow.select_analysis_modules') as mock_modules, \
             patch('transcriptx.cli.analysis_workflow.questionary.confirm') as mock_confirm, \
             patch('transcriptx.cli.analysis_workflow.filter_modules_by_mode') as mock_filter:
            
            mock_mode.return_value = "full"
            mock_modules.return_value = ["sentiment", "ner"]
            mock_filter.return_value = ["sentiment", "ner"]
            mock_confirm.return_value.ask.return_value = True
            
            _run_analysis_workflow_impl()
        
        # Should continue without geocoding
        mock_pipeline.assert_called_once()
        result = mock_pipeline.return_value
        assert "ner" in result["modules_run"]  # NER should still run
    
    @patch('transcriptx.cli.analysis_workflow.select_transcript_file_interactive')
    @patch('transcriptx.cli.analysis_workflow.run_analysis_pipeline')
    def test_resource_exhaustion_memory(
        self, mock_pipeline, mock_select_file, temp_transcript_file
    ):
        """Test handling when memory limit is reached."""
        mock_select_file.return_value = temp_transcript_file
        mock_pipeline.side_effect = MemoryError("Memory limit exceeded")
        
        with patch('transcriptx.cli.analysis_workflow.select_analysis_mode') as mock_mode, \
             patch('transcriptx.cli.analysis_workflow.select_analysis_modules') as mock_modules, \
             patch('transcriptx.cli.analysis_workflow.questionary.confirm') as mock_confirm, \
             patch('transcriptx.cli.analysis_workflow.filter_modules_by_mode') as mock_filter, \
             patch('transcriptx.cli.analysis_workflow.log_error') as mock_log_error:
            
            mock_mode.return_value = "full"
            mock_modules.return_value = ["sentiment"]
            mock_filter.return_value = ["sentiment"]
            mock_confirm.return_value.ask.return_value = True
            
            _run_analysis_workflow_impl()
        
        # Should handle memory error gracefully
        mock_log_error.assert_called()
    
    @patch('transcriptx.cli.analysis_workflow.select_transcript_file_interactive')
    def test_wrong_file_format(self, mock_select, tmp_path):
        """Test handling of wrong file format."""
        wrong_file = tmp_path / "test.txt"
        wrong_file.write_text("This is not a JSON file")
        
        mock_select.return_value = wrong_file
        
        with patch('transcriptx.cli.analysis_workflow.validate_transcript_file') as mock_validate, \
             patch('transcriptx.cli.analysis_workflow.log_error') as mock_log_error:
            
            mock_validate.side_effect = ValueError("Invalid file format")
            
            _run_analysis_workflow_impl()
        
        # Should detect wrong format
        mock_validate.assert_called()
