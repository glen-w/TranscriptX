"""
Speaker utilities for TranscriptX.

This module provides utilities for working with speaker names and mappings.
"""

from typing import Optional, Tuple

from transcriptx.utils.text_utils import is_named_speaker


def get_display_speaker_name(speaker_id: str | int) -> str | None:
    """
    Returns the speaker name if it is a named speaker, otherwise None.

    This is a simple utility that checks if a speaker ID is already a named speaker.
    For database-driven speaker identification, use get_speaker_display_name() from
    transcriptx.core.utils.speaker_extraction instead.

    Args:
        speaker_id: The speaker ID (name or identifier)

    Returns:
        The speaker name if it's a named speaker, or None otherwise.
    """
    # If speaker_id is already a named speaker, return it directly
    if is_named_speaker(str(speaker_id)):
        return str(speaker_id)

    return None


def parse_speaker_name(full_name: str) -> Tuple[str, Optional[str]]:
    """
    Parse a full speaker name into first name and surname.

    Splits input like "Glen Wright" into first_name="Glen", surname="Wright".
    Handles single names (surname is None) and multiple words
    (first word = first_name, rest = surname).

    Args:
        full_name: Full name string (e.g., "Glen Wright", "John", "Mary Jane Smith")

    Returns:
        Tuple of (first_name, surname) where surname may be None

    Examples:
        >>> parse_speaker_name("Glen Wright")
        ('Glen', 'Wright')
        >>> parse_speaker_name("John")
        ('John', None)
        >>> parse_speaker_name("Mary Jane Smith")
        ('Mary', 'Jane Smith')
    """
    if not full_name:
        return ("", None)

    # Strip whitespace
    full_name = full_name.strip()

    # Split by spaces
    parts = full_name.split()

    if len(parts) == 0:
        return ("", None)
    elif len(parts) == 1:
        # Single name - use as first_name, no surname
        return (parts[0], None)
    else:
        # Multiple words - first word is first_name, rest is surname
        first_name = parts[0]
        surname = " ".join(parts[1:])
        return (first_name, surname)


def format_speaker_display_name(
    first_name: Optional[str] = None,
    surname: Optional[str] = None,
    display_name: Optional[str] = None,
    name: Optional[str] = None,
) -> str:
    """
    Format speaker display name with priority: display_name > first_name+surname > name.

    Args:
        first_name: First name
        surname: Surname
        display_name: Custom display name (highest priority)
        name: Fallback name

    Returns:
        Formatted display name
    """
    if display_name:
        return display_name

    if first_name and surname:
        return f"{first_name} {surname}"
    elif first_name:
        return first_name
    elif name:
        return name

    return "Unknown"
