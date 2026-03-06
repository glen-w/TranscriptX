"""
Minimal CLI tests for stable entry points (help and subcommands).

These tests are not quarantined and cover argument parsing and --help
for the main app and key subcommands. For full main flow tests see test_main.py.
"""

import pytest

pytestmark = [pytest.mark.smoke]

from transcriptx.cli.main import app
from typer.testing import CliRunner


@pytest.fixture
def cli_runner():
    """Typer test client for CLI."""
    return CliRunner()


class TestCLIHelpStable:
    """Stable CLI help and subcommand tests (no interactive flow)."""

    def test_app_help_returns_zero_and_shows_name(self, cli_runner):
        """--help exits 0 and mentions TranscriptX."""
        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "TranscriptX" in result.stdout or "transcriptx" in result.stdout.lower()

    def test_database_subcommand_help(self, cli_runner):
        """database --help succeeds."""
        result = cli_runner.invoke(app, ["database", "--help"])
        assert result.exit_code == 0
        assert "database" in result.stdout.lower()

    def test_transcript_subcommand_help(self, cli_runner):
        """transcript --help succeeds."""
        result = cli_runner.invoke(app, ["transcript", "--help"])
        assert result.exit_code == 0
        assert "transcript" in result.stdout.lower()

    def test_cross_session_subcommand_help(self, cli_runner):
        """cross-session --help succeeds."""
        result = cli_runner.invoke(app, ["cross-session", "--help"])
        assert result.exit_code == 0
        assert (
            "cross-session" in result.stdout.lower()
            or "cross_session" in result.stdout.lower()
        )

    def test_analyze_subcommand_help(self, cli_runner):
        """analyze --help succeeds."""
        result = cli_runner.invoke(app, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "analyze" in result.stdout.lower()
