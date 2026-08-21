"""Duplicate library execute: fingerprint guard, companions, slug retarget."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.app.duplicate_cleanup.models import (
    CONFIRM_DELETE_DUPLICATES,
    DuplicateAuthorization,
)
from transcriptx.app.duplicate_cleanup.service import DuplicateCleanupService
from transcriptx.core.utils import slug_manager


def _v1_doc(text: str) -> dict:
    return {
        "schema_version": 1,
        "source": {
            "type": "manual",
            "original_path": "test.json",
            "imported_at": "2020-01-01T00:00:00+00:00",
        },
        "metadata": {
            "duration_seconds": 1.0,
            "segment_count": 1,
            "speaker_count": 1,
            "word_count": 1,
        },
        "segments": [
            {"speaker": "SPEAKER_00", "text": text, "start": 0.0, "end": 1.0},
        ],
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _auth(plan_id: str) -> DuplicateAuthorization:
    return DuplicateAuthorization(
        acknowledged=True,
        phrase=CONFIRM_DELETE_DUPLICATES,
        plan_id=plan_id,
    )


@pytest.fixture
def transcript_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    transcripts = tmp_path / "transcripts"
    metadata = transcripts / "metadata"
    readable = transcripts / "readable"
    originals = transcripts / "originals"
    for path in (transcripts, metadata, readable, originals):
        path.mkdir(parents=True)

    import transcriptx.core.audio.linked_transcripts as linked
    import transcriptx.io.import_metadata.paths as import_paths

    monkeypatch.setattr(linked, "DIARISED_TRANSCRIPTS_DIR", transcripts)
    monkeypatch.setattr(linked, "READABLE_TRANSCRIPTS_DIR", readable)
    monkeypatch.setattr(linked, "TRANSCRIPTS_ORIGINALS_DIR", originals)
    monkeypatch.setattr(
        linked,
        "speaker_map_sidecar_candidates",
        lambda transcript: [
            Path(transcript).with_name(f"{Path(transcript).stem}.speaker_map.json")
        ],
    )
    monkeypatch.setattr(import_paths, "DIARISED_TRANSCRIPTS_DIR", transcripts)
    monkeypatch.setattr(import_paths, "TRANSCRIPTS_METADATA_DIR", metadata)

    state_file = tmp_path / "processing_state.json"
    state_file.write_text('{"processed_files": {}}', encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE", state_file
    )
    index_path = tmp_path / ".transcriptx_index.json"
    monkeypatch.setattr(slug_manager, "INDEX_FILE", index_path)
    return {
        "transcripts": transcripts,
        "readable": readable,
        "originals": originals,
        "index": index_path,
        "state_file": state_file,
    }


def test_execute_deletes_extra_keeps_keeper(transcript_roots, tmp_path: Path) -> None:
    transcripts = transcript_roots["transcripts"]
    keeper = transcripts / "keep.json"
    extra = transcripts / "drop.json"
    payload = _v1_doc("same")
    _write_json(keeper, payload)
    _write_json(extra, payload)
    sidecar = extra.with_name("drop.speaker_map.json")
    sidecar.write_text("{}", encoding="utf-8")
    readable = transcript_roots["readable"] / "drop.txt"
    readable.write_text("hello", encoding="utf-8")
    run_dir = tmp_path / "outputs" / "drop" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "run_results.json").write_text("{}", encoding="utf-8")

    slug_manager.register_transcript(
        "sha256:shared",
        str(extra),
        source_basename="drop",
        source_path=str(extra),
    )

    from transcriptx.app.corpus_inventory.models import (
        AnalysisState,
        AnalysisStatus,
        CorrectionsState,
        CorrectionsStatus,
        FieldIntegrity,
        FileStamp,
        InventoryFingerprint,
        InventoryRow,
        SpeakerIdState,
        SpeakerIdStatus,
    )

    def _fp(path: Path) -> InventoryFingerprint:
        return InventoryFingerprint(stamps=(FileStamp(str(path), 0, 0),))

    def _row(path: Path, *, rich: bool) -> InventoryRow:
        return InventoryRow(
            transcript_path=path,
            transcript_key=None,
            slug=path.stem,
            title=path.stem,
            imported_at=None,
            duration_seconds=None,
            speaker_count=None,
            word_count=None,
            source_id=None,
            listing_integrity=FieldIntegrity.OK,
            speaker=SpeakerIdState(
                SpeakerIdStatus.COMPLETE if rich else SpeakerIdStatus.NONE,
                FieldIntegrity.OK,
            ),
            corrections=CorrectionsState(
                CorrectionsStatus.COMPLETE if rich else CorrectionsStatus.NEVER_STARTED,
                FieldIntegrity.OK,
                accepted_count=2 if rich else 0,
            ),
            analysis=AnalysisState(
                AnalysisStatus.COMPLETED if rich else AnalysisStatus.UNANALYSED,
                FieldIntegrity.OK,
                modules_succeeded=3 if rich else None,
                modules_eligible=3 if rich else None,
            ),
            last_activity_at=None,
            fingerprint=_fp(path),
        )

    rows = {
        str(keeper.resolve()): _row(keeper, rich=True),
        str(extra.resolve()): _row(extra, rich=False),
    }
    svc = DuplicateCleanupService(
        audio_paths=[],
        transcript_paths=[keeper, extra],
        inventory_rows=lambda _paths: rows,
    )
    preview = svc.preview()
    result = svc.execute(preview, _auth(preview.plan_id))
    assert result.ok
    assert result.transcripts_deleted == 1
    assert keeper.exists()
    assert not extra.exists()
    assert not sidecar.exists()
    assert not readable.exists()
    assert run_dir.exists()
    index = json.loads(transcript_roots["index"].read_text(encoding="utf-8"))
    entry = index["transcripts"]["sha256:shared"]
    assert Path(entry["source_path"]).resolve() == keeper.resolve()
    assert "drop" not in index.get("slug_to_key", {}) or index["slug_to_key"].get(
        entry["slug"]
    ) == "sha256:shared"


def test_execute_refuses_stale_fingerprint(tmp_path: Path) -> None:
    recordings = tmp_path / "rec"
    recordings.mkdir()
    a = recordings / "a.mp3"
    b = recordings / "b.mp3"
    a.write_bytes(b"aa")
    b.write_bytes(b"aa")
    svc = DuplicateCleanupService(
        audio_paths=[a, b],
        transcript_paths=[],
        inventory_rows=lambda _paths: {},
    )
    preview = svc.preview()
    extra = preview.groups[0].extras[0].fingerprint.path
    extra.write_bytes(b"changed-bytes")
    result = svc.execute(preview, _auth(preview.plan_id))
    assert extra.exists()
    assert result.skipped
    assert result.audio_deleted == 0


def test_execute_requires_phrase(tmp_path: Path) -> None:
    recordings = tmp_path / "rec"
    recordings.mkdir()
    a = recordings / "a.mp3"
    b = recordings / "b.mp3"
    a.write_bytes(b"aa")
    b.write_bytes(b"aa")
    svc = DuplicateCleanupService(
        audio_paths=[a, b],
        transcript_paths=[],
        inventory_rows=lambda _paths: {},
    )
    preview = svc.preview()
    result = svc.execute(
        preview,
        DuplicateAuthorization(True, "delete duplicates", preview.plan_id),
    )
    assert not result.ok
    assert a.exists() and b.exists()


def test_does_not_delete_archived_original_of_keeper(
    transcript_roots, tmp_path: Path
) -> None:
    transcripts = transcript_roots["transcripts"]
    recordings = tmp_path / "rec"
    recordings.mkdir()
    keeper_audio = recordings / "keep.mp3"
    extra_audio = recordings / "dup.mp3"
    keeper_audio.write_bytes(b"same")
    extra_audio.write_bytes(b"same")
    keeper_tx = transcripts / "keep.json"
    _write_json(keeper_tx, _v1_doc("hello"))
    sidecar = keeper_tx.with_name("keep.import_meta.json")
    _write_json(
        sidecar,
        {
            "schema_version": 1,
            "import_id": "11111111-1111-1111-1111-111111111111",
            "imported_at": "2020-01-01T00:00:00+00:00",
            "adapter_source_id": "manual",
            "source_upload_basename": "keep.mp3",
            "archived_original_relpath": str(keeper_audio),
            "current_json_filename": "keep.json",
            "rename_history": [],
        },
    )
    svc = DuplicateCleanupService(
        audio_paths=[keeper_audio, extra_audio],
        transcript_paths=[keeper_tx],
        inventory_rows=lambda _paths: {},
        find_linked=lambda path: [keeper_tx] if path == keeper_audio else [],
    )
    preview = svc.preview()
    extras = {
        extra.fingerprint.path.resolve()
        for group in preview.groups
        for extra in group.extras
    }
    assert extra_audio.resolve() in extras
    assert keeper_audio.resolve() not in extras
    result = svc.execute(preview, _auth(preview.plan_id))
    assert result.ok
    assert keeper_audio.exists()
    assert keeper_tx.exists()
    assert not extra_audio.exists()
