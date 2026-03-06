"""
Utility functions for TranscriptX.

This module provides common utility functions used across the TranscriptX
codebase, including text processing, formatting, and helper functions.
"""

from .html_utils import create_html_report, generate_html_report
from .simple_progress import progress, log_progress, log_warning, log_error, log_success
from .text_utils import format_time, is_named_speaker, normalize_text

__all__ = [
    # Progress utilities
    "progress",
    "log_progress",
    "log_warning",
    "log_error",
    "log_success",
    # Text utilities
    "is_named_speaker",
    "format_time",
    "normalize_text",
    # HTML utilities
    "create_html_report",
    "generate_html_report",
]
