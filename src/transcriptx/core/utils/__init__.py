"""
Utils module for TranscriptX core functionality.

This module contains all utility components including:
- Configuration management
- Logging utilities
- NLP utilities
- Output standards and validation
- Path management
- Transcript processing utilities
"""

# Import config directly (always available)
from .config import *


# Lazy imports for modules that may have heavy dependencies
def get_logger():
    """Lazy import for logger module."""
    from . import logger

    return logger


def get_nlp_utils():
    """Lazy import for nlp_utils module."""
    from . import nlp_utils

    return nlp_utils


def get_output_standards():
    """Lazy import for output_standards module."""
    from . import output_standards

    return output_standards


def get_output_validation():
    """Lazy import for output_validation module."""
    from . import output_validation

    return output_validation


def get_paths():
    """Lazy import for paths module."""
    from . import paths

    return paths


def get_simplify_transcript():
    """Lazy import for simplify_transcript module."""
    from . import simplify_transcript

    return simplify_transcript


def get_transcript_output():
    """Lazy import for transcript_output module."""
    from . import transcript_output

    return transcript_output


def get_understandability():
    """Lazy import for understandability module."""
    from . import understandability

    return understandability


def get_validation():
    """Lazy import for validation module."""
    from . import validation

    return validation


__all__ = [
    "config",
    "get_logger",
    "get_nlp_utils",
    "get_output_standards",
    "get_output_validation",
    "get_paths",
    "get_simplify_transcript",
    "get_transcript_output",
    "get_understandability",
    "get_validation",
]
