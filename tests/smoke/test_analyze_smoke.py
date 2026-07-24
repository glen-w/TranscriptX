"""Smoke test: run analysis pipeline on fixture and verify output files."""

import json
import os
import shutil
from pathlib import Path

import pytest

from transcriptx.io.speaker_map_resolver import sidecar_path_for


@pytest.mark.smoke
def test_analyze_smoke_outputs(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    transcript_src = repo_root / "tests" / "fixtures" / "data" / "tiny_diarized.json"
    transcript_path = tmp_path / "tiny_diarized.json"
    shutil.copy(transcript_src, transcript_path)
    sidecar_path = sidecar_path_for(transcript_path)
    sidecar_path.write_text(
        json.dumps(
            {
                "speaker_map_schema_version": 1,
                "speaker_map": {
                    "SPEAKER_00": "Speaker 1",
                    "SPEAKER_01": "Speaker 2",
                },
                "ignored_speakers": [],
                "speaker_id_to_db_id": {},
                "speaker_map_provenance": {"source": "test"},
            }
        ),
        encoding="utf-8",
    )

    output_root = tmp_path / "outputs"
    output_root.mkdir()

    os.environ["TRANSCRIPTX_USE_EMOJIS"] = "0"
    os.environ["TRANSCRIPTX_DISABLE_DOWNLOADS"] = "1"
    os.environ["TRANSCRIPTX_OUTPUT_DIR"] = str(output_root)

    from transcriptx.app.models.requests import AnalysisRequest
    from transcriptx.app.workflows.analysis import run_analysis

    request = AnalysisRequest(
        transcript_path=transcript_path,
        mode="quick",
        modules=["stats"],
        output_dir=output_root,
    )
    result = run_analysis(request)
    assert result.success, result.errors

    any_files = [p for p in output_root.rglob("*") if p.is_file()]
    assert any_files, "Expected at least one output file in output tree"

    report_artifacts = [
        path
        for path in output_root.rglob("*")
        if path.is_file()
        and path.suffix in {".txt", ".md", ".json", ".csv"}
        and path.stat().st_size > 0
        and (
            path.name in {"report.json", "report.md", "report.txt"}
            or "/stats/" in path.as_posix()
        )
    ]
    assert report_artifacts, "Expected non-empty stats/report output"
