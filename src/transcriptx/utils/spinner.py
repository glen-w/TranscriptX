"""
Spinner utilities for TranscriptX.

This module provides context managers and utilities for showing progress
indicators during long-running operations.
"""

import contextlib
import os
import sys

from transcriptx.utils.text_utils import strip_emojis

try:
    from yaspin import yaspin

    YASPIN_AVAILABLE = True
except ImportError:
    YASPIN_AVAILABLE = False


@contextlib.contextmanager
def suppress_stdout_stderr():
    """
    Suppresses all output to stdout and stderr.
    Useful for silencing noisy libraries like transformers.
    """
    with open(os.devnull, "w") as devnull:
        old_stdout, old_stderr = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = devnull, devnull
            yield
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr


@contextlib.contextmanager
def spinner(text: str = "Processing...", disable: bool = False):
    """
    Context manager for showing a spinner while a block of code runs.

    Args:
        text: Text to display with the spinner
        disable: Whether to disable the spinner (useful for CI environments)
    """
    if not YASPIN_AVAILABLE or disable:
        # Fallback: just print the text
        print(strip_emojis(f"🔄 {text}"))
        try:
            yield
            print(strip_emojis(f"✅ {text} - completed"))
        except Exception as e:
            print(strip_emojis(f"❌ {text} - failed: {e}"))
            raise e
    else:
        with yaspin(text=text) as sp:
            try:
                yield
                sp.ok("✅")
            except Exception as e:
                sp.fail("💥")
                raise e


def simple_spinner(text: str = "Processing..."):
    """
    Simple spinner that just prints status messages.
    Useful when yaspin is not available.
    """
    print(strip_emojis(f"🔄 {text}"))
    return contextlib.nullcontext()


# --- Spinner Manager for Synchronization ---
class SpinnerManager:
    """
    Singleton manager to track the currently active spinner and allow pausing/resuming.
    """

    _instance = None
    _active_spinner = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def set_active_spinner(cls, spinner):
        cls._active_spinner = spinner

    @classmethod
    def clear_active_spinner(cls):
        cls._active_spinner = None

    @classmethod
    def pause_spinner(cls):
        if cls._active_spinner:
            cls._active_spinner.pause()

    @classmethod
    def resume_spinner(cls):
        if cls._active_spinner:
            cls._active_spinner.resume()


class Spinner:
    """
    A simple spinner class for showing progress during long-running operations.

    This class provides a context manager interface for showing progress
    with optional text updates.
    """

    def __init__(self, text: str = "Processing...", disable: bool = False):
        """
        Initialize the spinner.

        Args:
            text: Initial text to display
            disable: Whether to disable the spinner
        """
        self.text = text
        self.disable = disable
        self._spinner = None
        self._paused = False

    def __enter__(self):
        """Enter the spinner context."""
        if not self.disable and YASPIN_AVAILABLE:
            self._spinner = yaspin(text=self.text)
            self._spinner.__enter__()
        else:
            print(strip_emojis(f"🔄 {self.text}"))
        SpinnerManager.set_active_spinner(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the spinner context."""
        SpinnerManager.clear_active_spinner()
        if self._spinner:
            if exc_type is None:
                self._spinner.ok("✅")
            else:
                self._spinner.fail("💥")
            self._spinner.__exit__(exc_type, exc_val, exc_tb)
        elif exc_type is None:
            print(strip_emojis(f"✅ {self.text} - completed"))
        else:
            print(strip_emojis(f"❌ {self.text} - failed: {exc_val}"))

    def update_text(self, text: str):
        """
        Update the spinner text.

        Args:
            text: New text to display
        """
        self.text = text
        if self._spinner and hasattr(self._spinner, "text"):
            self._spinner.text = text
        elif not self.disable:
            print(strip_emojis(f"🔄 {text}"))

    def ok(self, text: str = "✅"):
        """
        Mark the spinner as successful.

        Args:
            text: Success text to display
        """
        if self._spinner:
            self._spinner.ok(text)
        elif not self.disable:
            print(strip_emojis(f"✅ {self.text} - {text}"))

    def fail(self, text: str = "💥"):
        """
        Mark the spinner as failed.

        Args:
            text: Failure text to display
        """
        if self._spinner:
            self._spinner.fail(text)
        elif not self.disable:
            print(strip_emojis(f"❌ {self.text} - {text}"))

    def pause(self):
        if self._spinner and not self._paused:
            self._spinner.stop()
            self._paused = True

    def resume(self):
        if self._spinner and self._paused:
            self._spinner.start()
            self._paused = False
