"""Smoke test: run analysis pipeline on fixture and verify output files."""

import os
import shutil
from pathlib import Path

import pytest


@pytest.mark.smoke
def test_analyze_smoke_outputs(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    transcript_src = repo_root / "tests" / "fixtures" / "data" / "tiny_diarized.json"
    transcript_path = tmp_path / "tiny_diarized.json"
    shutil.copy(transcript_src, transcript_path)

    output_root = tmp_path / "outputs"
    output_root.mkdir()

    os.environ["TRANSCRIPTX_USE_EMOJIS"] = "0"
    os.environ["TRANSCRIPTX_DB_ENABLED"] = "0"
    os.environ["TRANSCRIPTX_DISABLE_DOWNLOADS"] = "1"
    os.environ["TRANSCRIPTX_OUTPUT_DIR"] = str(output_root)

    from transcriptx.app.models.requests import AnalysisRequest
    from transcriptx.app.workflows.analysis import run_analysis

    request = AnalysisRequest(
        transcript_path=transcript_path,
        mode="quick",
        modules=["stats"],
        skip_speaker_mapping=True,
        output_dir=output_root,
    )
    result = run_analysis(request)
    assert result.success, result.errors

    any_files = [p for p in output_root.rglob("*") if p.is_file()]
    assert any_files, "Expected at least one output file in output tree"

    stats_files = [
        path
        for path in output_root.rglob("*")
        if path.is_file()
        and "stats" in path.as_posix()
        and path.suffix in {".txt", ".md"}
        and path.stat().st_size > 0
    ]
    assert stats_files, "Expected non-empty stats summary output"
