"""Integration tests for corrections studio roundtrip integration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.store import corrections_session_store as store_mod
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    create_transcript_document,
)
from transcriptx.services.corrections_studio.service import CorrectionService

pytestmark = pytest.mark.integration_core


def _write_transcript(path: Path) -> None:
    doc = create_transcript_document(
        [
            {
                "speaker": "SPEAKER_00",
                "text": "teh quick brown fox",
                "start": 0.0,
                "end": 1.0,
            },
            {
                "speaker": "SPEAKER_01",
                "text": "jumps over teh dog",
                "start": 1.0,
                "end": 2.0,
            },
        ],
        SourceInfo(
            type="manual",
            original_path="originals/sample.txt",
            imported_at="2026-01-01T00:00:00+00:00",
            file_hash="abc",
            file_mtime=0.0,
        ),
        TranscriptMetadata(duration_seconds=2.0, segment_count=2, speaker_count=2),
    )
    path.write_text(json.dumps(doc), encoding="utf-8")


def test_corrections_studio_file_backed_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corrections_root = tmp_path / "corrections"
    monkeypatch.setattr(store_mod, "_CORRECTIONS_ROOT", corrections_root)

    transcript = tmp_path / "sample.json"
    _write_transcript(transcript)

    svc = CorrectionService()
    session = svc.start_or_resume_session(str(transcript))
    assert session.session_id

    generated = svc.generate_candidates(session.session_id, force=True)
    listed = svc.list_candidates(session.session_id, offset=0, limit=500)
    assert isinstance(generated, list)
    assert listed == generated

    if listed:
        svc.record_decision(
            session.session_id,
            listed[0].candidate_id,
            decision="accept",
            selected_occurrence_keys=[
                o.stable_occurrence_key
                for o in listed[0].occurrences
                if o.stable_occurrence_key
            ],
        )

    preview = svc.compute_preview(session.session_id)
    assert isinstance(preview, dict)

    export_path = tmp_path / "exported.json"
    export_result = svc.apply_and_export(
        session.session_id, export_path=str(export_path)
    )
    assert isinstance(export_result, dict)
    assert export_path.exists()

    # File-backed persistence contract: session snapshot + index entries exist under corrections root.
    idx = corrections_root / "sessions" / "sessions_index.json"
    assert idx.exists()
    idx_data = json.loads(idx.read_text(encoding="utf-8"))
    assert session.session_id in idx_data.get("entries", {})

    rel = idx_data["entries"][session.session_id]["rel_path"]
    snap = corrections_root / "sessions" / rel / "session.json"
    events = corrections_root / "sessions" / rel / "events.jsonl"
    assert snap.exists()
    assert events.exists()


def test_corrections_studio_load_missing_session_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(store_mod, "_CORRECTIONS_ROOT", tmp_path / "corrections")
    svc = CorrectionService()
    assert svc.load_session("missing-session") is None
