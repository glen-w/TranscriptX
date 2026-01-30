"""
Output utilities for TranscriptX.

This module provides utilities for managing output, including suppression
of noisy library output and progress indicators.
"""

import contextlib
import os
import sys
from collections.abc import Generator

from transcriptx.core.utils.logger import get_logger
from transcriptx.utils.simple_progress import progress

logger = get_logger()


@contextlib.contextmanager
def suppress_stdout_stderr() -> Generator[None, None, None]:
    """
    Context manager to suppress all output to stdout and stderr.

    This utility is particularly useful for silencing noisy libraries
    (e.g., transformers, torch) during model loading or inference.
    It temporarily redirects stdout and stderr to /dev/null and then
    restores them when the context exits.

    Usage:
        with suppress_stdout_stderr():
            # Code that produces unwanted output
            model = load_noisy_model()
            result = model.predict(data)

    Note:
        This is a context manager, so it must be used with the 'with' statement.
        The original stdout/stderr are always restored, even if an exception occurs.
        This is especially useful when loading ML models that print progress bars
        or initialization messages that would clutter the user interface.
    """
    with open(os.devnull, "w") as devnull:
        old_stdout, old_stderr = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = devnull, devnull
            yield
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr


@contextlib.contextmanager
def spinner(text: str = "Processing...") -> Generator[None, None, None]:
    """
    Unified spinner context manager using the simplified progress system.

    Args:
        text: Text to display with the spinner
    """
    with progress(text):
        yield
