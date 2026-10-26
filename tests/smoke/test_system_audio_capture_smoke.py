"""PR-gate smoke: G5 host companion loads and prints help."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parent.parent.parent
    / "scripts"
    / "system-audio-capture.py"
)


@pytest.mark.smoke
def test_system_audio_capture_help():
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "BlackHole" in (proc.stdout or "")
    assert "probe" in (proc.stdout or "")
