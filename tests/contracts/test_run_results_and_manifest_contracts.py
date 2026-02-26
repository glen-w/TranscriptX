"""
Contract tests for run_results.json and manifest.json shape (golden run on mini_transcript).
Validates stable output contracts with Pydantic.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.pipeline.run_schema import (
    RunResultsSummary,
    validate_manifest_shape,
)
from transcriptx.core.pipeline.target_resolver import TranscriptRef
from transcriptx.core.utils import output_standards as output_standards_module
from transcriptx.core.utils import paths as paths_module
from transcriptx.core.utils import transcript_output as transcript_output_module


@pytest.fixture
def _patch_output_paths(tmp_path, monkeypatch):
    outputs_root = tmp_path / "outputs"
    transcripts_root = tmp_path / "transcripts"
    monkeypatch.setenv("TRANSCRIPTX_DISABLE_DOWNLOADS", "1")
    monkeypatch.setattr(paths_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(paths_module, "GROUP_OUTPUTS_DIR", str(outputs_root / "groups"))
    monkeypatch.setattr(output_standards_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(
        output_standards_module,
        "DIARISED_TRANSCRIPTS_DIR",
        str(transcripts_root),
    )
    monkeypatch.setattr(transcript_output_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(
        transcript_output_module,
        "DIARISED_TRANSCRIPTS_DIR",
        str(transcripts_root),
    )
    return outputs_root


def test_golden_run_stats_produces_valid_manifest_and_run_results(
    tmp_path, monkeypatch, _patch_output_paths
) -> None:
    """Run pipeline on mini_transcript with stats; assert manifest and run_results shape."""
    import transcriptx.core.pipeline.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "OUTPUTS_DIR", str(_patch_output_paths))

    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "tests" / "fixtures" / "mini_transcript.json"
    if not fixture_path.exists():
        pytest.skip("fixtures/mini_transcript.json not found")

    result = run_analysis_pipeline(
        target=TranscriptRef(path=str(fixture_path)),
        selected_modules=["stats"],
        persist=False,
    )

    assert result["errors"] == []
    output_dir = Path(result["output_dir"])
    assert output_dir.exists()

    # manifest.json: required shape and run_metadata
    manifest_path = output_dir / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_manifest_shape(manifest)
    assert "run_id" in manifest
    assert "artifacts" in manifest
    assert isinstance(manifest["artifacts"], list)

    # run_results.json: run/skip/fail summary
    run_results_path = output_dir / "run_results.json"
    assert run_results_path.exists()
    run_results_data = json.loads(run_results_path.read_text(encoding="utf-8"))
    summary = RunResultsSummary.validate_run_results(run_results_data)
    assert summary.run_id
    assert summary.transcript_key
    assert "stats" in summary.modules_run or "stats" in summary.modules_enabled
    assert summary.schema_version >= 1
