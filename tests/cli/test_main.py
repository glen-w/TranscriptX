"""
Tests for the main CLI entry point.

This module tests the main CLI interface including menu flow,
argument parsing, and subcommand routing.
"""

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit

from transcriptx.cli.main import app


class TestMainCLI:
    """Tests for main CLI entry point."""

    def test_cli_app_initialization(self):
        """Test that CLI app is properly initialized."""
        assert app is not None
        assert hasattr(app, "registered_commands")

    def test_cli_help(self, typer_test_client):
        """Test CLI help command."""
        result = typer_test_client.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "TranscriptX" in result.stdout or "transcriptx" in result.stdout.lower()

    def test_cli_main_with_config_option(
        self, typer_test_client, tmp_path, mock_config
    ):
        """Test interactive subcommand accepts --config option."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")
        with (
            patch("transcriptx.cli.main._run_interactive_setup_and_menu") as mock_impl,
            patch("transcriptx.cli.main.ensure_data_dirs"),
            patch("transcriptx.cli.main._configure_nltk_data_path"),
        ):
            result = typer_test_client.invoke(
                app, ["interactive", "--config", str(config_file)]
            )
            assert result.exit_code == 0
            mock_impl.assert_called_once()
            call_kwargs = mock_impl.call_args
            assert call_kwargs is not None

    def test_cli_main_with_log_level(self, typer_test_client, mock_config):
        """Test interactive subcommand accepts --log-level option."""
        with (
            patch("transcriptx.cli.main._run_interactive_setup_and_menu") as mock_impl,
            patch("transcriptx.cli.main.ensure_data_dirs"),
            patch("transcriptx.cli.main._configure_nltk_data_path"),
        ):
            result = typer_test_client.invoke(
                app, ["interactive", "--log-level", "DEBUG"]
            )
            assert result.exit_code == 0
            mock_impl.assert_called_once()

    def test_cli_main_with_output_dir(self, typer_test_client, tmp_path, mock_config):
        """Test interactive subcommand accepts --output-dir option."""
        with (
            patch("transcriptx.cli.main._run_interactive_setup_and_menu") as mock_impl,
            patch("transcriptx.cli.main.ensure_data_dirs"),
            patch("transcriptx.cli.main._configure_nltk_data_path"),
        ):
            result = typer_test_client.invoke(
                app, ["interactive", "--output-dir", str(tmp_path)]
            )
            assert result.exit_code == 0
            mock_impl.assert_called_once()

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
        assert (
            "cross-session" in result.stdout.lower()
            or "cross_session" in result.stdout.lower()
        )

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
        result = typer_test_client.invoke(app, ["web-viewer", "--help"])

        assert result.exit_code == 0


class TestMainImpl:
    """Tests for _run_interactive_setup_and_menu (main interactive entry point)."""

    @patch("transcriptx.cli.main.show_banner")
    @patch("transcriptx.cli.main.run_interactive_menu")
    @patch("transcriptx.cli.main._check_audio_playback_dependencies")
    def test_main_impl_interactive_menu(
        self, mock_audio, mock_menu, mock_banner, mock_config
    ):
        """Test interactive menu flow."""
        from transcriptx.cli.main import _run_interactive_setup_and_menu

        _run_interactive_setup_and_menu()

        mock_banner.assert_called_once()
        mock_menu.assert_called_once()

    @patch("transcriptx.cli.main.show_banner")
    @patch("transcriptx.cli.main.run_interactive_menu")
    @patch("transcriptx.cli.main._check_audio_playback_dependencies")
    def test_main_impl_analyze_choice(
        self, mock_audio, mock_menu, mock_banner, mock_config
    ):
        """Test that run_interactive_menu is called during setup."""
        from transcriptx.cli.main import _run_interactive_setup_and_menu

        _run_interactive_setup_and_menu()

        mock_menu.assert_called_once()

    @patch("transcriptx.cli.main.load_config")
    @patch("transcriptx.cli.main.show_banner")
    @patch("transcriptx.cli.main.run_interactive_menu")
    @patch("transcriptx.cli.main._check_audio_playback_dependencies")
    def test_main_impl_load_config(
        self, mock_audio, mock_menu, mock_banner, mock_load, tmp_path, mock_config
    ):
        """Test loading configuration file."""
        from transcriptx.cli.main import _run_interactive_setup_and_menu

        config_file = tmp_path / "config.json"
        config_file.write_text('{"test": "config"}')

        _run_interactive_setup_and_menu(config_file=config_file)

        mock_load.assert_called_once()
