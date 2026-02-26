"""
High-leverage integration tests.

These tests run real pipeline/config paths with minimal setup: one module
on a fixture transcript, config load, and output shape. No DB, no models.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.pipeline.target_resolver import TranscriptRef
from transcriptx.core.pipeline import pipeline as pipeline_module
from transcriptx.core.utils import paths as paths_module
from transcriptx.core.utils import output_standards as output_standards_module
from transcriptx.core.utils import transcript_output as transcript_output_module


@pytest.mark.integration_core
def test_pipeline_stats_module_produces_artifacts(tmp_path, monkeypatch) -> None:
    """Run pipeline with 'stats' module on mini transcript; assert no errors and output dir structure."""
    outputs_root = tmp_path / "outputs"
    transcripts_root = tmp_path / "transcripts"
    outputs_root.mkdir()
    transcripts_root.mkdir()

    monkeypatch.setenv("TRANSCRIPTX_DISABLE_DOWNLOADS", "1")
    monkeypatch.setattr(paths_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(paths_module, "GROUP_OUTPUTS_DIR", str(outputs_root / "groups"))
    monkeypatch.setattr(output_standards_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(
        output_standards_module, "DIARISED_TRANSCRIPTS_DIR", str(transcripts_root)
    )
    monkeypatch.setattr(transcript_output_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(
        transcript_output_module, "DIARISED_TRANSCRIPTS_DIR", str(transcripts_root)
    )
    monkeypatch.setattr(pipeline_module, "OUTPUTS_DIR", str(outputs_root))

    fixture_path = (
        Path(__file__).resolve().parents[2] / "fixtures" / "mini_transcript.json"
    )
    if not fixture_path.exists():
        pytest.skip("fixtures/mini_transcript.json not found")

    result = run_analysis_pipeline(
        target=TranscriptRef(path=str(fixture_path)),
        selected_modules=["stats"],
        persist=False,
    )

    assert result["errors"] == [], f"Pipeline errors: {result.get('errors')}"
    assert "output_dir" in result
    output_dir = Path(result["output_dir"])
    assert output_dir.exists()
    manifest_path = output_dir / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "artifacts" in manifest


@pytest.mark.integration_core
def test_pipeline_transcript_output_module_produces_files(
    tmp_path, monkeypatch
) -> None:
    """Run pipeline with 'transcript_output' on mini transcript; assert txt/csv outputs."""
    outputs_root = tmp_path / "outputs"
    transcripts_root = tmp_path / "transcripts"
    outputs_root.mkdir()
    transcripts_root.mkdir()

    monkeypatch.setenv("TRANSCRIPTX_DISABLE_DOWNLOADS", "1")
    monkeypatch.setattr(paths_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(paths_module, "GROUP_OUTPUTS_DIR", str(outputs_root / "groups"))
    monkeypatch.setattr(output_standards_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(
        output_standards_module, "DIARISED_TRANSCRIPTS_DIR", str(transcripts_root)
    )
    monkeypatch.setattr(transcript_output_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(
        transcript_output_module, "DIARISED_TRANSCRIPTS_DIR", str(transcripts_root)
    )
    monkeypatch.setattr(pipeline_module, "OUTPUTS_DIR", str(outputs_root))

    fixture_path = (
        Path(__file__).resolve().parents[2] / "fixtures" / "mini_transcript.json"
    )
    if not fixture_path.exists():
        pytest.skip("fixtures/mini_transcript.json not found")

    result = run_analysis_pipeline(
        target=TranscriptRef(path=str(fixture_path)),
        selected_modules=["transcript_output"],
        persist=False,
    )

    assert result["errors"] == []
    output_dir = Path(result["output_dir"])
    transcripts_dir = output_dir / "transcripts"
    assert transcripts_dir.exists()
    assert list(transcripts_dir.glob("*.txt")) or list(transcripts_dir.glob("*.csv"))
