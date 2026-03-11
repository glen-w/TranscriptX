"""Smoke tests: verify the web entry point is importable and functional."""

import sys
from pathlib import Path

import pytest


@pytest.mark.smoke
def test_web_entry_importable() -> None:
    """Verify the web entry point module is importable."""
    import importlib

    mod = importlib.import_module("transcriptx.web.__main__")
    assert callable(getattr(mod, "main", None))


@pytest.mark.smoke
def test_web_entry_help() -> None:
    """Verify the web entry point responds to --help without error."""
    import subprocess

    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "transcriptx.web", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "TranscriptX" in result.stdout or "transcriptx" in result.stdout.lower()
