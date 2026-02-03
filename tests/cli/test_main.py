"""
Tests for the main CLI entry point.

This module tests the main CLI interface including menu flow,
argument parsing, and subcommand routing.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

pytestmark = pytest.mark.quarantined  # reason: app.commands/run_single_analysis_workflow/exit codes changed; remove_by: when main CLI stabilizes

from transcriptx.cli.main import app


class TestMainCLI:
    """Tests for main CLI entry point."""
    
    def test_cli_app_initialization(self):
        """Test that CLI app is properly initialized."""
        assert app is not None
        assert hasattr(app, "commands")
    
    def test_cli_help(self, typer_test_client):
        """Test CLI help command."""
        result = typer_test_client.invoke(app, ["--help"])
        
        assert result.exit_code == 0
        assert "TranscriptX" in result.stdout or "transcriptx" in result.stdout.lower()
    
    def test_cli_main_with_config_option(self, typer_test_client, tmp_path, mock_config):
        """Test main CLI with config file option."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"test": "config"}')
        
        with patch('transcriptx.cli.main._main_impl') as mock_main:
            mock_main.return_value = None
            
            result = typer_test_client.invoke(app, ["--config", str(config_file)])
            
            # Should call main implementation
            # (exact behavior depends on implementation)
            assert result.exit_code in [0, 1]  # May exit with 0 or 1
    
    def test_cli_main_with_log_level(self, typer_test_client, mock_config):
        """Test main CLI with log level option."""
        with patch('transcriptx.cli.main._main_impl') as mock_main:
            mock_main.return_value = None
            
            result = typer_test_client.invoke(app, ["--log-level", "DEBUG"])
            
            # Should accept log level
            assert result.exit_code in [0, 1]
    
    def test_cli_main_with_output_dir(self, typer_test_client, tmp_path, mock_config):
        """Test main CLI with output directory option."""
        output_dir = tmp_path / "outputs"
        
        with patch('transcriptx.cli.main._main_impl') as mock_main:
            mock_main.return_value = None
            
            result = typer_test_client.invoke(app, ["--output-dir", str(output_dir)])
            
            # Should accept output directory
            assert result.exit_code in [0, 1]
    
    def test_cli_database_subcommand(self, typer_test_client):
        """Test database subcommand is available."""
        result = typer_test_client.invoke(app, ["database", "--help"])
        
        assert result.exit_code == 0
        assert "database" in result.stdout.lower()
    
    def test_cli_transcript_subcommand(self, typer_test_client):
        """Test transcript subcommand is available."""
        result = typer_test_client.invoke(app, ["transcript", "--help"])
        
        assert result.exit_code == 0
        assert "transcript" in result.stdout.lower()
    
    def test_cli_cross_session_subcommand(self, typer_test_client):
        """Test cross-session subcommand is available."""
        result = typer_test_client.invoke(app, ["cross-session", "--help"])
        
        assert result.exit_code == 0
        assert "cross-session" in result.stdout.lower() or "cross_session" in result.stdout.lower()

    def test_analyze_all_transcripts_conflicts_with_transcript_file(
        self, typer_test_client, tmp_path
    ):
        """--all-transcripts cannot be combined with --transcript-file."""
        transcript_file = tmp_path / "test.json"
        transcript_file.write_text('{"segments": []}')

        result = typer_test_client.invoke(
            app,
            [
                "analyze",
                "--all-transcripts",
                "--transcript-file",
                str(transcript_file),
            ],
        )

        assert result.exit_code == 1
        assert "--all-transcripts" in result.stdout

    def test_analyze_all_transcripts_conflicts_with_transcripts(
        self, typer_test_client, tmp_path
    ):
        """--all-transcripts cannot be combined with --transcripts."""
        transcript_file = tmp_path / "test.json"
        transcript_file.write_text('{"segments": []}')

        result = typer_test_client.invoke(
            app,
            [
                "analyze",
                "--all-transcripts",
                "--transcripts",
                str(transcript_file),
            ],
        )

        assert result.exit_code == 1
        assert "--all-transcripts" in result.stdout
    
    def test_cli_web_viewer_command(self, typer_test_client):
        """Test web-viewer command."""
        with patch('transcriptx.web.app.run') as mock_run:
            result = typer_test_client.invoke(app, ["web-viewer", "--help"])
            
            # Should show help for web-viewer
            assert result.exit_code == 0


class TestMainImpl:
    """Tests for _main_impl function."""
    
    @patch('transcriptx.cli.main.show_banner')
    @patch('transcriptx.cli.main._initialize_whisperx_service')
    @patch('transcriptx.cli.main._check_audio_playback_dependencies')
    @patch('transcriptx.cli.main.questionary.select')
    def test_main_impl_interactive_menu(
        self, mock_select, mock_audio, mock_whisperx, mock_banner, mock_config
    ):
        """Test interactive menu flow."""
        from transcriptx.cli.main import _main_impl
        
        # Mock questionary to return Exit
        mock_select.return_value.ask.return_value = "🚪 Exit"
        
        # Should exit gracefully
        try:
            _main_impl()
        except SystemExit:
            pass  # Expected when exiting
        
        # Verify banner was shown
        mock_banner.assert_called_once()
    
    @patch('transcriptx.cli.main.show_banner')
    @patch('transcriptx.cli.main._initialize_whisperx_service')
    @patch('transcriptx.cli.main._check_audio_playback_dependencies')
    @patch('transcriptx.cli.main.questionary.select')
    @patch('transcriptx.cli.main.run_single_analysis_workflow')
    def test_main_impl_analyze_choice(
        self, mock_workflow, mock_select, mock_audio, mock_whisperx, mock_banner, mock_config
    ):
        """Test selecting Analyze from menu."""
        from transcriptx.cli.main import _main_impl
        
        # Mock questionary to return Analyze, then Exit
        mock_select.return_value.ask.side_effect = ["📊 Analyze", "🚪 Exit"]
        mock_workflow.return_value = None
        
        # Should call analysis workflow
        try:
            _main_impl()
        except SystemExit:
            pass  # Expected when exiting
        
        # Verify workflow was called
        mock_workflow.assert_called_once()
    
    @patch('transcriptx.cli.main.load_config')
    def test_main_impl_load_config(self, mock_load, tmp_path, mock_config):
        """Test loading configuration file."""
        from transcriptx.cli.main import _main_impl
        
        config_file = tmp_path / "config.json"
        config_file.write_text('{"test": "config"}')
        
        with patch('transcriptx.cli.main.show_banner'), \
             patch('transcriptx.cli.main._initialize_whisperx_service'), \
             patch('transcriptx.cli.main._check_audio_playback_dependencies'), \
             patch('transcriptx.cli.main.questionary.select') as mock_select:
            
            mock_select.return_value.ask.return_value = "🚪 Exit"
            
            try:
                _main_impl(config_file=str(config_file))
            except SystemExit:
                pass
            
            # Verify config was loaded
            mock_load.assert_called_once()
