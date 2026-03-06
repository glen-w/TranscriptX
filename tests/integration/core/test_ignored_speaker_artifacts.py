from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from transcriptx.core.pipeline import pipeline as pipeline_module
from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.pipeline.target_resolver import TranscriptRef
from transcriptx.core.utils import output_standards as output_standards_module
from transcriptx.core.utils import paths as paths_module
from transcriptx.core.utils._path_core import get_canonical_base_name
from transcriptx.core.utils import transcript_output as transcript_output_module


def _write_transcript(path: Path) -> None:
    payload = {
        "segments": [
            {"speaker": "Alice", "text": "Hello from Alice", "start": 0.0, "end": 1.0},
            {"speaker": "Bob", "text": "Hello from Bob", "start": 1.0, "end": 2.0},
        ],
        "ignored_speakers": ["Alice"],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_ignored_speaker_creates_no_speaker_artifacts(
    tmp_path: Path, monkeypatch: Any
) -> None:
    outputs_root = tmp_path / "outputs"
    transcripts_root = tmp_path / "transcripts"
    transcripts_root.mkdir(parents=True, exist_ok=True)

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

    transcript_path = transcripts_root / "ignored_transcript.json"
    _write_transcript(transcript_path)

    result = run_analysis_pipeline(
        target=TranscriptRef(path=str(transcript_path)),
        selected_modules=["stats"],
        persist=False,
    )

    assert result["errors"] == []
    output_dir = Path(result["output_dir"])
    base_name = get_canonical_base_name(str(transcript_path))
    stats_json = output_dir / f"{base_name}_stats.json"
    assert stats_json.exists()
    payload = json.loads(stats_json.read_text(encoding="utf-8"))

    speakers = payload.get("speakers", [])
    assert all(speaker.get("name") != "Alice" for speaker in speakers)
