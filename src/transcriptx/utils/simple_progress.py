"""
Simplified progress feedback for TranscriptX.

This module provides a clean, simple way to show progress during long-running operations.
It focuses on the core need: letting users know something is happening.
"""

import contextlib
from typing import Generator

try:
    from yaspin import yaspin

    YASPIN_AVAILABLE = True
except ImportError:
    YASPIN_AVAILABLE = False


@contextlib.contextmanager
def progress(message: str = "Processing...") -> Generator[None, None, None]:
    """
    Simple progress indicator for long-running operations.

    This is the main interface for showing progress. It uses a spinner when available,
    or simple text messages as fallback.

    Args:
        message: Description of what's happening

    Example:
        with progress("Loading models..."):
            # do work here
            pass
    """
    if YASPIN_AVAILABLE:
        # Use yaspin for nice animated spinner
        with yaspin(text=message) as sp:
            try:
                yield
                sp.ok("✅")
            except Exception:
                sp.fail("❌")
                raise
    else:
        # Simple fallback: just print start and end messages
        print(f"🔄 {message}")
        try:
            yield
            print(f"✅ {message} - completed")
        except Exception as e:
            print(f"❌ {message} - failed: {e}")
            raise


def log_progress(message: str) -> None:
    """
    Log a progress message without interfering with spinners.

    This is for informational messages that should appear during long operations.
    It doesn't try to control spinners, just prints the message.

    Args:
        message: Progress message to display
    """
    print(f"ℹ️  {message}")


def log_warning(message: str) -> None:
    """
    Log a warning message.

    Args:
        message: Warning message to display
    """
    print(f"⚠️  {message}")


def log_error(message: str) -> None:
    """
    Log an error message.

    Args:
        message: Error message to display
    """
    print(f"❌ {message}")


def log_success(message: str) -> None:
    """
    Log a success message.

    Args:
        message: Success message to display
    """
    print(f"✅ {message}")
