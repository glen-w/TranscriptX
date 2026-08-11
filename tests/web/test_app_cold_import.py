"""Cold-import contracts for Streamlit app startup weight."""

from __future__ import annotations

import subprocess
import sys


def test_import_web_app_does_not_load_insights_blocks() -> None:
    """Eager app import must not pull the heavy blocks implementation graph."""
    code = """
import sys
import transcriptx.web.app  # noqa: F401
heavy = "transcriptx.web.blocks.implementations.insights"
corrections = "transcriptx.web.page_modules.corrections_studio"
transcript = "transcriptx.web.page_modules.transcript"
assert heavy not in sys.modules, heavy
assert corrections not in sys.modules, corrections
assert transcript not in sys.modules, transcript
# Package may be present without auto-registering implementations.
assert "transcriptx.web.blocks.builtin" not in sys.modules
print("ok")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ok" in result.stdout


def test_ensure_builtin_blocks_loads_insights_graph() -> None:
    code = """
import sys
from transcriptx.web.blocks.builtin import register_builtin_blocks
register_builtin_blocks()
assert "transcriptx.web.blocks.implementations.insights" in sys.modules
print("ok")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ok" in result.stdout
