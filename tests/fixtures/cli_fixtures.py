"""
CLI fixtures for testing.

This module provides fixtures for CLI-related testing, including
Typer test clients, questionary mocks, and workflow mocks.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import MagicMock

import pytest


def create_mock_typer_app():
    """Create a mock Typer app for testing."""
    mock_app = MagicMock()
    return mock_app


def create_mock_questionary_responses():
    """Create mock questionary responses for testing."""
    return {
        "select": MagicMock(return_value=MagicMock(ask=MagicMock(return_value=None))),
        "confirm": MagicMock(return_value=MagicMock(ask=MagicMock(return_value=False))),
        "text": MagicMock(return_value=MagicMock(ask=MagicMock(return_value=""))),
        "path": MagicMock(return_value=MagicMock(ask=MagicMock(return_value=""))),
    }


def create_mock_workflow_result(
    success: bool = True, output_dir: str = "/tmp/test_output"
):
    """Create a mock workflow result."""
    if success:
        return {"status": "success", "output_dir": output_dir, "errors": []}
    else:
        return {"status": "error", "output_dir": None, "errors": ["Test error"]}


def create_mock_file_selection_result(file_path: Path = None):
    """Create a mock file selection result."""
    if file_path is None:
        file_path = Path("/tmp/test_transcript.json")

    return {"file_path": str(file_path), "selected": True, "exists": True}


@pytest.fixture
def cli_runner():
    """
    Fixture for running CLI commands and capturing output.

    Uses Typer's CliRunner for better integration with the CLI.
    """
    from typer.testing import CliRunner

    from transcriptx.cli.main import app

    runner = CliRunner()

    def _run(
        command: str,
        args: List[str],
        stdin=None,
        timeout: Optional[int] = None,
        env: Optional[Dict[str, str]] = None,
    ):
        """
        Run a CLI command.

        Args:
            command: CLI command name (e.g., "analyze") or flag (e.g., "--help")
            args: List of arguments
            stdin: stdin input (not used with CliRunner, but kept for compatibility)
            timeout: Timeout in seconds (not used with CliRunner, but kept for compatibility)
            env: Environment variables

        Returns:
            Result object with returncode, stdout, stderr attributes
        """
        # Merge environment
        if env:
            full_env = os.environ.copy()
            full_env.update(env)
        else:
            full_env = None

        # Build command list
        if command.startswith("--"):
            # Global flags
            cmd_args = [command] + args
        else:
            # Subcommands
            cmd_args = [command] + args

        # Run with CliRunner
        result = runner.invoke(app, cmd_args, env=full_env)

        # Convert to similar format as subprocess.CompletedProcess
        class Result:
            def __init__(self, typer_result):
                self.returncode = (
                    typer_result.exit_code if typer_result.exit_code is not None else 0
                )
                self.stdout = typer_result.stdout
                self.stderr = ""  # Typer combines output
                self.success = typer_result.exit_code == 0

        return Result(result)

    return _run


@pytest.fixture
def non_interactive_env():
    """
    Fixture that provides environment with non-interactive mode enabled.

    Returns:
        Dict with TRANSCRIPTX_NON_INTERACTIVE=1
    """
    return {"TRANSCRIPTX_NON_INTERACTIVE": "1"}
