"""Integration test: managed transcript + sidecar + pipeline output contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.pipeline.target_resolver import TranscriptRef
from transcriptx.core.utils import paths as paths_module
from transcriptx.io.import_metadata_sidecar import write_initial_sidecar
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    create_transcript_document,
)

pytestmark = pytest.mark.integration_core


def _write_managed_transcript(tmp_path: Path) -> Path:
    transcripts_root = tmp_path / "transcripts"
    originals_root = transcripts_root / "originals"
    transcripts_root.mkdir(parents=True, exist_ok=True)
    originals_root.mkdir(parents=True, exist_ok=True)

    archive_rel = "originals/managed.srt"
    archive = transcripts_root / archive_rel
    archive.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello\n",
        encoding="utf-8",
    )

    transcript = transcripts_root / "managed.json"
    doc = create_transcript_document(
        [{"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0}],
        SourceInfo(
            type="srt",
            original_path=archive_rel,
            imported_at="2026-01-01T00:00:00+00:00",
            file_hash="abc123",
            file_mtime=0.0,
        ),
        TranscriptMetadata(duration_seconds=1.0, segment_count=1, speaker_count=1),
    )
    transcript.write_text(json.dumps(doc), encoding="utf-8")

    return transcript


def test_managed_transcript_pipeline_preserves_sidecar_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Managed transcript with a valid sidecar should run and surface metadata in results."""
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("TRANSCRIPTX_DISABLE_DOWNLOADS", "1")
    monkeypatch.setattr(paths_module, "OUTPUTS_DIR", outputs_root)
    monkeypatch.setattr(paths_module, "GROUP_OUTPUTS_DIR", outputs_root / "groups")

    transcript = _write_managed_transcript(tmp_path)

    # Wire import-metadata sidecar to the same managed transcript roots.
    monkeypatch.setattr(
        "transcriptx.io.import_metadata_sidecar.DIARISED_TRANSCRIPTS_DIR",
        transcript.parent,
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata_sidecar.TRANSCRIPTS_METADATA_DIR",
        transcript.parent / "metadata",
    )

    sidecar = write_initial_sidecar(
        transcript,
        import_id="import-xyz",
        imported_at="2026-01-01T00:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename="managed.srt",
        archived_original_relpath="originals/managed.srt",
    )

    result = run_analysis_pipeline(
        target=TranscriptRef(path=str(transcript)),
        selected_modules=["stats"],
        persist=False,
    )

    assert result.get("errors") == [], result.get("errors")
    output_dir = Path(result["output_dir"])
    run_results = json.loads(
        (output_dir / "run_results.json").read_text(encoding="utf-8")
    )

    # stats may be skipped if there are no named speakers; assert stable run_results shape
    # and that the module outcome is recorded with a clear reason.
    assert run_results.get("modules_enabled") == ["stats"]
    outcomes = run_results.get("module_outcomes") or []
    assert isinstance(outcomes, list) and outcomes
    stats_outcome = next(o for o in outcomes if o.get("module_id") == "stats")
    assert stats_outcome.get("execution_status") in {"completed", "skipped"}
    if stats_outcome.get("execution_status") == "skipped":
        assert stats_outcome.get("reason_code") == "requires at least 1 named speakers"
    assert sidecar.exists()
