"""Smoke test: run pipeline on fixture transcript to verify install + run path."""

import os
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
    assert result.success, f"Analysis failed: {result.errors}"

    files = [p for p in output_root.rglob("*") if p.is_file()]
    assert files, "Expected at least one output file"
