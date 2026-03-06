"""
Capture stdout/stderr from legacy code that still prints.

This is transitional compatibility glue, not a permanent logging
architecture. Remove once printing is eliminated from workflow functions.
"""

from __future__ import annotations

import contextlib
import io


@contextlib.contextmanager
def capture_output():
    """Capture stdout/stderr from legacy code that still prints."""
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        yield stdout_buf, stderr_buf
