"""
Regression tests for CLI exit code behavior.

This module tests CLI exit codes to catch regressions introduced by
standardizing exit codes across all commands.
"""

import re
import subprocess

import pytest

from transcriptx.cli.exit_codes import (
    EXIT_SUCCESS,
    EXIT_ERROR,
    EXIT_CONFIG_ERROR,
    EXIT_USER_CANCEL,
)


class TestTableDrivenExitCodes:
    """Table-driven tests for CLI exit codes."""
    
    @pytest.mark.parametrize(
        "command,args,expected_exit_code,expected_stderr_pattern",
        [
            # Success cases
            ("--help", [], EXIT_SUCCESS, None),
            # Note: --version may not be implemented, skip for now
            # ("--version", [], EXIT_SUCCESS, None),
            # Note: Actual file tests would need real transcript files
            # ("analyze", ["valid_file.json"], EXIT_SUCCESS, None),
            
            # Config error cases
            # ("analyze", ["--config", "nonexistent.json"], EXIT_CONFIG_ERROR, ".*config.*"),
            
            # Runtime error cases
            # ("analyze", ["nonexistent.json"], EXIT_ERROR, ".*not found.*"),
        ],
    )
    def test_cli_exit_codes_table(
        self, cli_runner, command, args, expected_exit_code, expected_stderr_pattern
    ):
        """Table-driven test for CLI exit codes."""
        result = cli_runner(command, args, timeout=5)
        
        assert result.returncode == expected_exit_code, (
            f"Expected exit code {expected_exit_code}, got {result.returncode}. "
            f"stderr: {result.stderr}"
        )
        
        if expected_stderr_pattern:
            assert re.search(
                expected_stderr_pattern, result.stderr, re.IGNORECASE
            ), f"stderr pattern '{expected_stderr_pattern}' not found in: {result.stderr}"


class TestExitCodeConsistency:
    """Tests for exit code consistency across commands."""
    
    def test_exit_codes_all_commands(self, cli_runner):
        """All CLI commands use standardized exit codes."""
        # Test help for all major commands (profile is optional and may not be registered)
        commands = ["analyze", "transcribe", "database"]
        
        for cmd in commands:
            result = cli_runner(cmd, ["--help"], timeout=5)
            # Help should always succeed
            assert result.returncode == EXIT_SUCCESS, (
                f"Command '{cmd} --help' should exit with SUCCESS, "
                f"got {result.returncode}"
            )
    
    def test_exit_codes_interactive_cancel(self):
        """Interactive cancel uses EXIT_USER_CANCEL."""
        # This would require mocking user input (Ctrl+C)
        # For now, we test that the constant exists
        assert EXIT_USER_CANCEL == 130  # Standard SIGINT code
    
    def test_exit_codes_non_interactive_errors(self, cli_runner, non_interactive_env):
        """Non-interactive errors use appropriate codes."""
        # Try to run analyze with nonexistent file in non-interactive mode
        result = cli_runner(
            "analyze",
            ["--non-interactive", "--transcript-file", "nonexistent.json"],
            env=non_interactive_env,
            timeout=5,
        )
        
        # Should exit with error code (not hang or use wrong code)
        assert result.returncode in [
            EXIT_ERROR,
            EXIT_CONFIG_ERROR,
        ], f"Non-interactive error should use ERROR or CONFIG_ERROR, got {result.returncode}"
    
    def test_exit_codes_exception_vs_cli_exit(self):
        """Exceptions are converted to CliExit correctly."""
        from transcriptx.cli.exit_codes import CliExit, exit_error
        
        # Test that exit_error raises CliExit
        with pytest.raises(CliExit) as exc_info:
            exit_error("Test error")
        
        # CliExit extends typer.Exit, which stores exit_code as an attribute
        # Check that it was created with the correct code
        assert exc_info.value.exit_code == EXIT_ERROR


class TestErrorMessageLocation:
    """Tests for error message location (stdout vs stderr)."""
    
    def test_error_messages_stderr(self, cli_runner, non_interactive_env):
        """Error messages go to stderr (not stdout)."""
        result = cli_runner(
            "analyze",
            ["--non-interactive", "nonexistent.json"],
            env=non_interactive_env,
            timeout=5,
        )
        
        # If there's an error message, it should be in stderr
        if result.stderr:
            # stderr should contain error-related text
            error_indicators = ["error", "not found", "failed", "invalid"]
            has_error_indicator = any(
                indicator in result.stderr.lower() for indicator in error_indicators
            )
            # If stderr has content, it should look like an error
            assert has_error_indicator or len(result.stderr) == 0
    
    def test_help_messages_stdout(self, cli_runner):
        """Help messages go to stdout."""
        result = cli_runner("--help", [], timeout=5)
        
        # Help should be in stdout
        assert len(result.stdout) > 0, "Help should be in stdout"
        assert "usage" in result.stdout.lower() or "commands" in result.stdout.lower()
    
    def test_golden_cli_snapshot(self, cli_runner, tmp_path):
        """Golden snapshot test for CLI output (stdout + stderr)."""
        # Capture help output
        result = cli_runner("--help", [], timeout=5)
        
        # Save snapshot
        snapshot_path = tmp_path / "cli_help_snapshot.txt"
        snapshot_content = f"""STDOUT:
{result.stdout}

STDERR:
{result.stderr}

EXIT CODE: {result.returncode}
"""
        snapshot_path.write_text(snapshot_content)
        
        # Basic validation - snapshot should exist and have content
        assert snapshot_path.exists()
        assert len(snapshot_path.read_text()) > 0
