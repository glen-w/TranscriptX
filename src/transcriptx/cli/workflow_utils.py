"""
Utilities for workflow execution modes.

This module provides utilities for detecting and handling interactive
vs non-interactive workflow modes.
"""

import os
from typing import Any, Optional


# Global flag for non-interactive mode (can be set by CLI)
_non_interactive_mode: Optional[bool] = None


def set_non_interactive_mode(enabled: bool = True) -> None:
    """
    Set non-interactive mode globally.

    When enabled, workflows should skip all user prompts and use
    defaults or fail if required input is missing.

    Args:
        enabled: Whether to enable non-interactive mode
    """
    global _non_interactive_mode
    _non_interactive_mode = enabled


def is_non_interactive() -> bool:
    """
    Check if non-interactive mode is enabled.

    Returns:
        True if non-interactive mode is enabled, False otherwise

    Note:
        Also checks TRANSCRIPTX_NON_INTERACTIVE environment variable
    """
    global _non_interactive_mode

    # Check global flag first
    if _non_interactive_mode is not None:
        return _non_interactive_mode

    # Check environment variable
    env_value = os.environ.get("TRANSCRIPTX_NON_INTERACTIVE", "").lower()
    if env_value in ("1", "true", "yes", "on"):
        return True

    return False


def require_interactive() -> None:
    """
    Raise an error if non-interactive mode is enabled.

    Use this in workflows that require user interaction.

    Raises:
        RuntimeError: If non-interactive mode is enabled
    """
    if is_non_interactive():
        raise RuntimeError(
            "This operation requires interactive mode. "
            "Run without --non-interactive flag or set TRANSCRIPTX_NON_INTERACTIVE=0"
        )


def get_default_or_fail(value: Optional[Any], default: Any, param_name: str) -> Any:
    """
    Get a value or default, failing in non-interactive mode if value is None.

    Args:
        value: The value to check (may be None)
        default: Default value to use if value is None
        param_name: Name of the parameter (for error message)

    Returns:
        value if not None, otherwise default

    Raises:
        ValueError: If value is None and non-interactive mode is enabled
    """
    if value is not None:
        return value

    if is_non_interactive():
        if default is None:
            raise ValueError(
                f"Parameter '{param_name}' is required in non-interactive mode"
            )
        return default

    return default
