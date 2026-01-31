import os
import sys
import subprocess
from pathlib import Path

import pytest


@pytest.mark.smoke
def test_analyze_smoke_outputs(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    transcript_src = repo_root / "tests" / "fixtures" / "data" / "tiny_diarized.json"
    transcript_path = tmp_path / "tiny_diarized.json"
    transcript_path.write_text(transcript_src.read_text(encoding="utf-8"), encoding="utf-8")

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
        str(transcript_path),
        "--modules",
        "stats",
        "--mode",
        "quick",
        "--non-interactive",
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
        timeout=60,
    )
    assert result.returncode == 0, result.stderr

    any_files = [p for p in output_root.rglob("*") if p.is_file()]
    assert any_files, "Expected at least one output file in output tree"

    stats_files = [
        path for path in output_root.rglob("*")
        if path.is_file() and "stats" in path.as_posix()
        and path.suffix in {".txt", ".md"}
        and path.stat().st_size > 0
    ]
    assert stats_files, "Expected non-empty stats summary output"
