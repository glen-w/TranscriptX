"""Stage 2: SpeakerProfileService ops — idempotency, stale update, corrupt link."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from transcriptx.core.speaker_profiles.errors import (
    CorruptLinkError,
    LinkConflictError,
    StaleUpdateError,
)
from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.layout import link_path
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.store_io import profile_content_sha256
from transcriptx.io.import_metadata_sidecar import write_initial_sidecar
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    create_transcript_document,
)

IMPORT_A = "550e8400-e29b-41d4-a716-446655440000"
IMPORT_B = "660e8400-e29b-41d4-a716-446655440001"


def _patch_roots(
    monkeypatch: pytest.MonkeyPatch, transcripts_root: Path
) -> None:
    metadata_dir = transcripts_root / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR",
        transcripts_root,
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR",
        metadata_dir,
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.file_discovery.DIARISED_TRANSCRIPTS_DIR",
        transcripts_root,
    )


def _write_managed(
    transcripts_root: Path,
    *,
    name: str,
    import_id: str,
    segments: list[dict[str, Any]] | None = None,
) -> Path:
    originals = transcripts_root / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    archive_rel = f"originals/{name}.srt"
    (transcripts_root / archive_rel).write_text("x", encoding="utf-8")
    segs = segments or [
        {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
        {"speaker": "SPEAKER_01", "text": "World", "start": 1.0, "end": 2.0},
    ]
    doc = create_transcript_document(
        segs,
        SourceInfo(
            type="srt",
            original_path=archive_rel,
            imported_at="2026-01-15T10:00:00+00:00",
            file_hash="abc",
            file_mtime=0.0,
        ),
        TranscriptMetadata(
            duration_seconds=2.0, segment_count=len(segs), speaker_count=2
        ),
    )
    path = transcripts_root / f"{name}.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    write_initial_sidecar(
        path,
        import_id=import_id,
        imported_at="2026-01-15T10:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename=f"{name}.srt",
        archived_original_relpath=archive_rel,
    )
    return path


def _service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transcripts_root: Path
) -> SpeakerProfileService:
    profiles_root = tmp_path / "speaker_profiles"
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    profiles_root.mkdir(parents=True, exist_ok=True)
    resolver = ManagedTranscriptResolver(
        transcripts_dir=transcripts_root, discovery_root=transcripts_root
    )
    return SpeakerProfileService(
        root=profiles_root, state_dir=state_dir, resolver=resolver
    )


@pytest.mark.unit
def test_create_profile_and_link_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch_roots(monkeypatch, transcripts)
    _write_managed(transcripts, name="meeting", import_id=IMPORT_A)
    svc = _service(tmp_path, monkeypatch, transcripts)

    key = str(uuid4())
    first = svc.create_profile_and_link(
        operation_idempotency_key=key,
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    second = svc.create_profile_and_link(
        operation_idempotency_key=key,
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    assert first.outcome.replayed is False
    assert second.outcome.replayed is True
    assert first.profile_id == second.profile_id
    assert first.link_id == second.link_id
    assert svc.get_profile(first.profile_id).display_name == "Alice"
    # Only one link file
    link_key = link_file_key(IMPORT_A, "SPEAKER_00")
    assert link_path(link_key, root=svc.root).is_file()


@pytest.mark.unit
def test_unlink_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch_roots(monkeypatch, transcripts)
    _write_managed(transcripts, name="meeting", import_id=IMPORT_A)
    svc = _service(tmp_path, monkeypatch, transcripts)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    unlink_key = str(uuid4())
    first = svc.unlink(
        operation_idempotency_key=unlink_key,
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    second = svc.unlink(
        operation_idempotency_key=unlink_key,
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    assert first.outcome.replayed is False
    assert second.outcome.replayed is True
    assert first.link_id == created.link_id
    link_key = link_file_key(IMPORT_A, "SPEAKER_00")
    assert svc.get_live_link(link_key) is None


@pytest.mark.unit
def test_relink_to_existing_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch_roots(monkeypatch, transcripts)
    _write_managed(transcripts, name="meeting", import_id=IMPORT_A)
    svc = _service(tmp_path, monkeypatch, transcripts)
    a = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    b = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Bob",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_01",
    )
    result = svc.relink(
        operation_idempotency_key=str(uuid4()),
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
        profile_id=b.profile_id,
    )
    link = svc.get_live_link(link_file_key(IMPORT_A, "SPEAKER_00"))
    assert link is not None
    assert link.profile_id == b.profile_id
    assert link.link_id == result.link_id
    assert link.link_id != a.link_id


@pytest.mark.unit
def test_stale_profile_update_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch_roots(monkeypatch, transcripts)
    _write_managed(transcripts, name="meeting", import_id=IMPORT_A)
    svc = _service(tmp_path, monkeypatch, transcripts)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    sha = profile_content_sha256(created.profile_id, root=svc.root)
    assert sha is not None
    svc.update_profile(
        operation_idempotency_key=str(uuid4()),
        profile_id=created.profile_id,
        expected_content_sha256=sha,
        display_name="Alice A.",
    )
    with pytest.raises(StaleUpdateError):
        svc.update_profile(
            operation_idempotency_key=str(uuid4()),
            profile_id=created.profile_id,
            expected_content_sha256=sha,
            display_name="Stale",
        )


@pytest.mark.unit
def test_corrupt_live_link_blocks_new_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch_roots(monkeypatch, transcripts)
    _write_managed(transcripts, name="meeting", import_id=IMPORT_B)
    svc = _service(tmp_path, monkeypatch, transcripts)
    key = link_file_key(IMPORT_B, "SPEAKER_00")
    path = link_path(key, root=svc.root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(CorruptLinkError):
        svc.create_profile_and_link(
            operation_idempotency_key=str(uuid4()),
            display_name="Alice",
            managed_transcript_id=IMPORT_B,
            local_speaker_key="SPEAKER_00",
        )


@pytest.mark.unit
def test_link_conflict_when_already_linked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch_roots(monkeypatch, transcripts)
    _write_managed(transcripts, name="meeting", import_id=IMPORT_A)
    svc = _service(tmp_path, monkeypatch, transcripts)
    svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    with pytest.raises(LinkConflictError):
        svc.create_profile_and_link(
            operation_idempotency_key=str(uuid4()),
            display_name="Alice2",
            managed_transcript_id=IMPORT_A,
            local_speaker_key="SPEAKER_00",
        )


@pytest.mark.unit
def test_event_filename_equals_idempotency_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch_roots(monkeypatch, transcripts)
    _write_managed(transcripts, name="meeting", import_id=IMPORT_A)
    svc = _service(tmp_path, monkeypatch, transcripts)
    result = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    assert len(result.event_ids) == 1
    event_path = svc.root / "events" / f"{result.event_ids[0]}.speaker_event.json"
    assert event_path.is_file()
    payload = json.loads(event_path.read_text(encoding="utf-8"))
    assert payload["event_id"] == payload["idempotency_id"] == result.event_ids[0]
    # staging cleaned after complete
    assert not (svc.root / "operations" / result.outcome.operation_id).exists()
