from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.pipeline import pipeline as pipeline_module
from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.pipeline.target_resolver import TranscriptRef
from transcriptx.core.utils import output_standards as output_standards_module
from transcriptx.core.utils import paths as paths_module
from transcriptx.core.utils import transcript_output as transcript_output_module


def test_pipeline_happy_path_minimal(tmp_path, monkeypatch) -> None:
    outputs_root = tmp_path / "outputs"
    transcripts_root = tmp_path / "transcripts"

    monkeypatch.setenv("TRANSCRIPTX_DISABLE_DOWNLOADS", "1")
    monkeypatch.setattr(paths_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(paths_module, "GROUP_OUTPUTS_DIR", str(outputs_root / "groups"))
    monkeypatch.setattr(output_standards_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(output_standards_module, "DIARISED_TRANSCRIPTS_DIR", str(transcripts_root))
    monkeypatch.setattr(transcript_output_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(transcript_output_module, "DIARISED_TRANSCRIPTS_DIR", str(transcripts_root))
    monkeypatch.setattr(pipeline_module, "OUTPUTS_DIR", str(outputs_root))

    fixture_path = Path(__file__).resolve().parents[2] / "fixtures" / "mini_transcript.json"
    result = run_analysis_pipeline(
        target=TranscriptRef(path=str(fixture_path)),
        selected_modules=["transcript_output"],
        persist=False,
    )

    assert result["errors"] == []
    output_dir = Path(result["output_dir"])
    assert output_dir.exists()

    manifest_path = output_dir / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "artifacts" in manifest
    assert len(manifest["artifacts"]) > 0

    transcripts_dir = output_dir / "transcripts"
    assert transcripts_dir.exists()
    assert list(transcripts_dir.glob("*.txt"))
    assert list(transcripts_dir.glob("*.csv"))
