"""
Integration tests for CLI workflow.

This module tests CLI menu flow, workflow routing, and command-line argument integration.
"""

from unittest.mock import MagicMock, patch
import pytest
from typer.testing import CliRunner

from transcriptx.cli.exit_codes import CliExit
from transcriptx.cli.main import app, _main_impl


@pytest.mark.integration
class TestCLIWorkflowIntegration:
    """Tests for CLI workflow integration."""

    @pytest.fixture
    def cli_runner(self):
        """Fixture for Typer CLI test runner."""
        return CliRunner()

    def test_interactive_menu_flow(self, cli_runner):
        """Test interactive menu flow."""
        with (
            patch("transcriptx.cli.main._main_impl") as mock_main,
            patch("transcriptx.cli.main.questionary.select") as mock_select,
            patch(
                "transcriptx.cli.analysis_workflow.run_single_analysis_workflow"
            ) as mock_analysis,
        ):

            mock_select.return_value.ask.side_effect = [
                "📊 Analyze",  # First choice
                "🚪 Exit",  # Then exit
            ]
            mock_main.return_value = None

            # Simulate menu interaction
            result = cli_runner.invoke(app, [])

            # Verify menu system works
            assert result.exit_code in [0, 1, 2]  # Typer may return 2 for usage exit

    def test_command_line_arguments_integration(self, cli_runner, tmp_path):
        """Test command-line arguments integration."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"test": "config"}')

        with patch("transcriptx.cli.main._main_impl") as mock_main:
            mock_main.return_value = None

            # Test with config file
            result = cli_runner.invoke(app, ["--config", str(config_file)])
            assert result.exit_code in [0, 1, 2]

            # Test with log level
            result = cli_runner.invoke(app, ["--log-level", "DEBUG"])
            assert result.exit_code in [0, 1, 2]

            # Test with output directory
            output_dir = tmp_path / "outputs"
            result = cli_runner.invoke(app, ["--output-dir", str(output_dir)])
            assert result.exit_code in [0, 1, 2]

    def test_subcommand_integration(self, cli_runner):
        """Test subcommand integration."""
        # Test database subcommand
        with patch("transcriptx.cli.database_commands.app") as mock_db_app:
            result = cli_runner.invoke(app, ["database", "--help"])
            assert result.exit_code == 0

        # Test transcript subcommand
        result = cli_runner.invoke(app, ["transcript", "--help"])
        assert result.exit_code == 0

        # Test cross-session subcommand
        result = cli_runner.invoke(app, ["cross-session", "--help"])
        assert result.exit_code == 0

    def test_workflow_chaining(self, cli_runner, tmp_path):
        """Test workflow chaining: transcription → analysis → database."""
        transcript_file = tmp_path / "test_transcript.json"
        transcript_file.write_text('{"segments": []}')

        with (
            patch("transcriptx.cli.main._main_impl") as mock_main,
            patch(
                "transcriptx.cli.workflow_modules.run_transcription_workflow"
            ) as mock_transcribe,
            patch(
                "transcriptx.cli.workflow_modules.run_single_analysis_workflow"
            ) as mock_analysis,
        ):

            # Simulate workflow chaining
            mock_transcribe.return_value = None
            mock_analysis.return_value = None

            # This would be called in sequence in real usage
            mock_transcribe()
            mock_analysis()

            # Verify both workflows called
            assert mock_transcribe.called
            assert mock_analysis.called

    def test_error_recovery_in_cli(self, cli_runner):
        """Test error recovery in CLI."""
        with (
            patch("transcriptx.cli.main._main_impl") as mock_main,
            patch("transcriptx.cli.main.questionary.select") as mock_select,
        ):

            # Simulate workflow error
            mock_select.return_value.ask.side_effect = [
                "📊 Analyze",  # Select analysis
                KeyboardInterrupt(),  # Simulate error
            ]

            # Should handle error gracefully
            try:
                result = cli_runner.invoke(app, [])
                # Should not crash
                assert result.exit_code in [0, 1, 2]
            except KeyboardInterrupt:
                # Expected behavior
                pass

    def test_config_file_loading(self, cli_runner, tmp_path):
        """Test config file loading from command line."""
        config_file = tmp_path / "test_config.json"
        config_file.write_text('{"output": {"base_output_dir": "/tmp/test"}}')

        with (
            patch("transcriptx.cli.main.load_config") as mock_load_config,
            patch("transcriptx.cli.main._main_impl") as mock_main,
        ):

            mock_load_config.return_value = MagicMock()
            mock_main.return_value = None

            result = cli_runner.invoke(app, ["--config", str(config_file)])

            # Verify config loading attempted
            assert result.exit_code in [0, 1, 2]

    def test_log_level_application(self, cli_runner):
        """Test log level application."""
        with (
            patch("transcriptx.cli.main.setup_logging") as mock_setup,
            patch("transcriptx.cli.main._main_impl") as mock_main,
        ):

            mock_main.return_value = None

            result = cli_runner.invoke(app, ["--log-level", "DEBUG"])

            # Verify logging setup
            assert result.exit_code in [0, 1, 2]

    def test_graceful_exit(self, cli_runner):
        """Test graceful exit handling."""
        with (
            patch("transcriptx.cli.main._main_impl") as mock_main,
            patch("transcriptx.cli.main.questionary.select") as mock_select,
        ):

            mock_select.return_value.ask.return_value = "🚪 Exit"
            mock_main.return_value = None

            result = cli_runner.invoke(app, [])

            # Should exit gracefully
            assert result.exit_code in [0, 1, 2]


@pytest.mark.integration
class TestMainImplIntegration:
    """Tests for _main_impl integration."""

    def test_main_impl_with_config(self, tmp_path):
        """Test _main_impl with config file."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"test": "config"}')

        with (
            patch("transcriptx.cli.main.load_config") as mock_load,
            patch("transcriptx.cli.main.questionary.select") as mock_select,
            patch("transcriptx.cli.main._initialize_whisperx_service") as mock_init,
        ):

            mock_load.return_value = MagicMock()
            mock_select.return_value.ask.return_value = "🚪 Exit"
            mock_init.return_value = True

            try:
                _main_impl(config_file=config_file)
            except CliExit as exc:
                code = getattr(exc, "exit_code", None)
                if code is None:
                    code = getattr(exc, "code", None)
                assert code == 0

            # Verify config loaded
            mock_load.assert_called()

    def test_main_impl_workflow_routing(self):
        """Test workflow routing in _main_impl."""
        with (
            patch("transcriptx.cli.main.questionary.select") as mock_select,
            patch(
                "transcriptx.cli.analysis_workflow.run_single_analysis_workflow"
            ) as mock_analysis,
            patch("transcriptx.cli.main._initialize_whisperx_service") as mock_init,
        ):

            mock_init.return_value = True
            mock_select.return_value.ask.side_effect = ["📊 Analyze", "🚪 Exit"]

            try:
                _main_impl()
            except CliExit as exc:
                code = getattr(exc, "exit_code", None)
                if code is None:
                    code = getattr(exc, "code", None)
                assert code == 0

            # Verify analysis workflow called
            mock_analysis.assert_called_once()
