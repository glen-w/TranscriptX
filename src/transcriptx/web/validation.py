"""
Input validation utilities for TranscriptX web interface.

This module provides validation functions for route handlers to ensure
all user inputs are validated before processing.
"""

import re
from typing import Optional

from transcriptx.core.utils.logger import get_logger

logger = get_logger()


def validate_session_name(session_name: str) -> tuple[bool, Optional[str]]:
    """
    Validate a session name.

    Session names should:
    - Not be empty
    - Not contain path traversal characters
    - Not be too long
    - Only contain safe characters

    Args:
        session_name: Session name to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not session_name:
        return False, "Session name cannot be empty"

    if len(session_name) > 255:
        return False, "Session name is too long (max 255 characters)"

    # Check for path traversal attempts
    if ".." in session_name or "/" in session_name or "\\" in session_name:
        return False, "Session name contains invalid characters"

    # Check for only safe characters (alphanumeric, underscore, hyphen, dot)
    if not re.match(r"^[a-zA-Z0-9_.-]+$", session_name):
        return False, "Session name contains invalid characters"

    return True, None


def validate_module_name(module_name: str) -> tuple[bool, Optional[str]]:
    """
    Validate an analysis module name.

    Args:
        module_name: Module name to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not module_name:
        return False, "Module name cannot be empty"

    if len(module_name) > 100:
        return False, "Module name is too long (max 100 characters)"

    # Check for path traversal attempts
    if ".." in module_name or "/" in module_name or "\\" in module_name:
        return False, "Module name contains invalid characters"

    # Allow alphanumeric and underscores (standard Python module naming)
    if not re.match(r"^[a-zA-Z0-9_]+$", module_name):
        return False, "Module name contains invalid characters"

    return True, None


def validate_speaker_id(speaker_id: any) -> tuple[bool, Optional[str]]:
    """
    Validate a speaker ID.

    Args:
        speaker_id: Speaker ID to validate (can be int or string)

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        speaker_id_int = int(speaker_id)
        if speaker_id_int < 1:
            return False, "Speaker ID must be a positive integer"
        return True, None
    except (ValueError, TypeError):
        return False, "Speaker ID must be a valid integer"


def validate_filename(filename: str) -> tuple[bool, Optional[str]]:
    """
    Validate a filename for safe file operations.

    Args:
        filename: Filename to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not filename:
        return False, "Filename cannot be empty"

    if len(filename) > 255:
        return False, "Filename is too long (max 255 characters)"

    # Check for path traversal attempts
    if ".." in filename or "/" in filename or "\\" in filename:
        return False, "Filename contains invalid characters"

    # Check for null bytes
    if "\x00" in filename:
        return False, "Filename contains null bytes"

    return True, None


def sanitize_session_name(session_name: str) -> str:
    """
    Sanitize a session name by removing dangerous characters.

    Args:
        session_name: Session name to sanitize

    Returns:
        Sanitized session name
    """
    # Remove path traversal and directory separators
    sanitized = session_name.replace("..", "").replace("/", "").replace("\\", "")

    # Remove any remaining dangerous characters
    sanitized = re.sub(r"[^a-zA-Z0-9_.-]", "", sanitized)

    return sanitized[:255]  # Limit length
