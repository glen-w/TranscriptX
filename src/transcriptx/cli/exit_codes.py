"""
Standardized exit codes for TranscriptX CLI commands.

This module provides consistent exit code handling across all CLI commands,
making it easier to test, script, and integrate TranscriptX with other tools.
"""

from typing import Optional

import typer


# Exit code constants
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_USER_CANCEL = 130  # Standard for SIGINT (Ctrl+C)


class CliExit(typer.Exit):
    """
    Standardized CLI exit exception that extends typer.Exit with consistent codes.

    This class provides a single way to exit CLI commands with predictable
    exit codes, making scripting and testing easier.

    Usage:
        raise CliExit.success()  # Success
        raise CliExit.error("Operation failed")  # Error with message
        raise CliExit.user_cancel()  # User cancelled
    """

    def __init__(self, code: int, message: Optional[str] = None):
        """
        Initialize CLI exit.

        Args:
            code: Exit code (use constants: EXIT_SUCCESS, EXIT_ERROR, etc.)
            message: Optional message to display before exiting
        """
        self.message = message
        super().__init__(code)
        if message:
            # Print message before exiting
            print(message)

    @classmethod
    def success(cls, message: Optional[str] = None) -> "CliExit":
        """Create a success exit."""
        return cls(EXIT_SUCCESS, message)

    @classmethod
    def error(cls, message: Optional[str] = None) -> "CliExit":
        """Create an error exit."""
        return cls(EXIT_ERROR, message)

    @classmethod
    def config_error(cls, message: Optional[str] = None) -> "CliExit":
        """Create a configuration error exit."""
        return cls(EXIT_CONFIG_ERROR, message)

    @classmethod
    def user_cancel(cls, message: Optional[str] = None) -> "CliExit":
        """Create a user cancellation exit."""
        return cls(EXIT_USER_CANCEL, message or "Operation cancelled by user")


def exit_success(message: Optional[str] = None) -> None:
    """Exit with success code."""
    raise CliExit.success(message)


def exit_error(message: Optional[str] = None) -> None:
    """Exit with error code."""
    raise CliExit.error(message)


def exit_config_error(message: Optional[str] = None) -> None:
    """Exit with configuration error code."""
    raise CliExit.config_error(message)


def exit_user_cancel(message: Optional[str] = None) -> None:
    """Exit with user cancellation code."""
    raise CliExit.user_cancel(message)
