"""Smoke test: run pipeline on fixture transcript to verify install + run path."""

import os
import sys
import subprocess
from pathlib import Path

import pytest


@pytest.mark.smoke
def test_pipeline_mini_transcript_smoke(tmp_path: Path) -> None:
    """Run analyze on mini_transcriptx.json with stats module (install verification)."""
    repo_root = Path(__file__).resolve().parents[2]
    transcript_path = repo_root / "tests" / "fixtures" / "mini_transcriptx.json"
    assert transcript_path.exists(), f"Fixture missing: {transcript_path}"

    output_root = tmp_path / "outputs"
    output_root.mkdir()

    env = os.environ.copy()
    env["TRANSCRIPTX_USE_EMOJIS"] = "0"
    env["TRANSCRIPTX_DB_ENABLED"] = "0"
    env["TRANSCRIPTX_DISABLE_DOWNLOADS"] = "1"
    env["TRANSCRIPTX_OUTPUT_DIR"] = str(output_root)

    cmd = [
        sys.executable,
        "-m",
        "transcriptx.cli.main",
        "analyze",
        "-t",
        str(transcript_path),
        "--modules",
        "stats",
        "--mode",
        "quick",
        "--skip-confirm",
        "--output-dir",
        str(output_root),
    ]

    result = subprocess.run(
        cmd,
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (result.stdout or "") + (result.stderr or "")

    files = [p for p in output_root.rglob("*") if p.is_file()]
    assert files, "Expected at least one output file"
