"""Tests for import surface."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_transcriptx_io_imports_cleanly_from_fresh_interpreter() -> None:
    """Importing io/core speaker helpers must not trigger a package-init cycle."""
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env["TRANSCRIPTX_DISABLE_DOWNLOADS"] = "1"

    code = """
import transcriptx.core as core
import transcriptx.io as io
from transcriptx.io.speaker_map_resolver import SpeakerMapResolver, sidecar_path_for
from transcriptx.core.pipeline.module_registry import get_available_modules

assert hasattr(core, "config")
assert callable(io.save_transcript)
assert SpeakerMapResolver.__name__ == "SpeakerMapResolver"
assert sidecar_path_for.__name__ == "sidecar_path_for"
assert isinstance(get_available_modules(), list)
print("ok")
"""

    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout
