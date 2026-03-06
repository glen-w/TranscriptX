"""
Smoke test: analysis pipeline runs without Docker or socket.

Validates that the core product (load transcript -> run modules -> write artifacts)
works with no Docker dependency. Used to guard against re-coupling to Docker.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.pipeline.target_resolver import TranscriptRef


@pytest.mark.smoke
def test_analysis_runs_without_docker(tmp_path, monkeypatch) -> None:
    """Load a fixture transcript, run stats module, assert outputs. No Docker socket needed."""
    from transcriptx.core.utils import output_standards as output_standards_module
    from transcriptx.core.utils import paths as paths_module
    from transcriptx.core.utils import transcript_output as transcript_output_module
    from transcriptx.core.pipeline import pipeline as pipeline_module

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
        Path(__file__).resolve().parents[2]
        / "tests"
        / "fixtures"
        / "mini_transcript.json"
    )
    assert fixture_path.exists(), f"Fixture missing: {fixture_path}"

    result = run_analysis_pipeline(
        target=TranscriptRef(path=str(fixture_path)),
        selected_modules=["stats"],
        persist=False,
    )

    assert result.get("errors") == [], result.get("errors")
    output_dir = Path(result["output_dir"])
    assert output_dir.exists()
    manifest_path = output_dir / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "artifacts" in manifest
