import os
import sys
import subprocess
from pathlib import Path

import pytest


@pytest.mark.smoke
def test_cli_help_smoke() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["TRANSCRIPTX_USE_EMOJIS"] = "0"
    env["TRANSCRIPTX_DISABLE_DOWNLOADS"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "transcriptx.cli.main", "--help"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    assert "TranscriptX" in result.stdout or "TranscriptX" in result.stderr
