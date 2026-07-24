"""Stage 3: recovery classification, read gating, retention, state_dir loss."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from transcriptx.core.speaker_profiles.errors import RepairRequiredError
from transcriptx.core.speaker_profiles.hashing import sha256_file
from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.layout import link_path, operation_path
from transcriptx.core.speaker_profiles.models import (
    OperationPlanActionV1,
    OperationPlanV1,
    SpeakerProfileOperationV1,
)
from transcriptx.core.speaker_profiles.operations import relative_link_path
from transcriptx.core.speaker_profiles.recovery import (
    classify_operation,
    recover_operation,
    retention_allows_cleanup,
)
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.store_io import (
    dumps_model,
    write_bytes_under_root,
    write_operation,
)
from transcriptx.io.import_metadata_sidecar import write_initial_sidecar
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    create_transcript_document,
)

IMPORT_A = "550e8400-e29b-41d4-a716-446655440000"


def _patch_roots(monkeypatch: pytest.MonkeyPatch, transcripts_root: Path) -> None:
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


def _write_managed(transcripts_root: Path, *, name: str, import_id: str) -> Path:
    originals = transcripts_root / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    archive_rel = f"originals/{name}.srt"
    (transcripts_root / archive_rel).write_text("x", encoding="utf-8")
    segs: list[dict[str, Any]] = [
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


def _svc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[SpeakerProfileService, Path]:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch_roots(monkeypatch, transcripts)
    _write_managed(transcripts, name="meeting", import_id=IMPORT_A)
    profiles_root = tmp_path / "speaker_profiles"
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    profiles_root.mkdir(parents=True, exist_ok=True)
    resolver = ManagedTranscriptResolver(
        transcripts_dir=transcripts, discovery_root=transcripts
    )
    svc = SpeakerProfileService(
        root=profiles_root, state_dir=state_dir, resolver=resolver
    )
    return svc, state_dir


@pytest.mark.unit
def test_complete_op_strips_workdir_keeps_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, _ = _svc(tmp_path, monkeypatch)
    result = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    op_id = result.outcome.operation_id
    assert not (svc.root / "operations" / op_id).exists()
    op_file = operation_path(op_id, root=svc.root)
    assert op_file.is_file()
    payload = json.loads(op_file.read_text(encoding="utf-8"))
    assert payload["phase"] == "complete"
    assert payload["receipt"] is not None
    assert retention_allows_cleanup(
        SpeakerProfileOperationV1.model_validate(payload)
    )


@pytest.mark.unit
def test_partial_unlink_blocks_reads_until_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, _ = _svc(tmp_path, monkeypatch)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    key = link_file_key(IMPORT_A, "SPEAKER_00")
    live = link_path(key, root=svc.root)
    before = sha256_file(live)
    assert before is not None

    # Simulate crash mid-unlink: event after-image applied, link delete not yet.
    op_id = str(uuid4())
    event_rel = f"events/{uuid4()}.speaker_event.json"
    event_bytes = b'{"version":1,"schema_id":"transcriptx.speaker_profile_event.v1",'
    event_bytes += (
        b'"event_id":"11111111-1111-1111-1111-111111111111",'
        b'"idempotency_id":"11111111-1111-1111-1111-111111111111",'
        b'"operation_idempotency_key":"22222222-2222-2222-2222-222222222222",'
        b'"event_type":"link_unlinked","created_at":"2026-01-01T00:00:00Z",'
        b'"actor":"user","payload":{}}\n'
    )
    # Use a minimal valid event via model instead
    from transcriptx.core.speaker_profiles.models import SpeakerProfileEventV1

    eid = str(uuid4())
    event = SpeakerProfileEventV1(
        event_id=eid,
        idempotency_id=eid,
        operation_idempotency_key=str(uuid4()),
        event_type="link_unlinked",
        created_at="2026-01-01T00:00:00Z",
    )
    event_rel = f"events/{eid}.speaker_event.json"
    event_bytes = dumps_model(event)
    from transcriptx.core.speaker_profiles.hashing import sha256_bytes

    write_bytes_under_root(svc.root / event_rel, event_bytes, root=svc.root)
    backup_rel = f"operations/{op_id}/backup/{relative_link_path(key)}"
    backup_path = svc.root / backup_rel
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_bytes(live.read_bytes())

    op = SpeakerProfileOperationV1(
        operation_id=op_id,
        operation_idempotency_key=str(uuid4()),
        op_type="unlink",
        phase="staged",
        plan=OperationPlanV1(
            actions=[
                OperationPlanActionV1(
                    action="write",
                    path=event_rel,
                    expected_before_sha256=None,
                    after_sha256=sha256_bytes(event_bytes),
                    staging_relpath=f"operations/{op_id}/staging/{event_rel}",
                ),
                OperationPlanActionV1(
                    action="delete",
                    path=relative_link_path(key),
                    expected_before_sha256=before,
                    after_sha256=None,
                    backup_relpath=backup_rel,
                ),
            ]
        ),
    )
    write_operation(op, root=svc.root)

    report = classify_operation(svc.root, op)
    assert report.recovery_class == "partial"
    assert report.blocking is True

    with pytest.raises(RepairRequiredError):
        svc.get_live_link(key)

    # Profile not in plan → still readable.
    assert svc.get_profile(created.profile_id) is not None

    from transcriptx.core.speaker_profiles.recovery import rollback_partial_to_before

    rollback_partial_to_before(svc.root, op)
    restored = svc.get_live_link(key)
    assert restored is not None
    assert restored.link_id == created.link_id
    # Event after-image removed on rollback of new write.
    assert not (svc.root / event_rel).exists()


@pytest.mark.unit
def test_needs_repair_retains_workdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, _ = _svc(tmp_path, monkeypatch)
    op_id = str(uuid4())
    staging = svc.root / "operations" / op_id / "staging"
    backup = svc.root / "operations" / op_id / "backup"
    staging.mkdir(parents=True)
    backup.mkdir(parents=True)
    (staging / "marker").write_text("x", encoding="utf-8")
    (backup / "marker").write_text("y", encoding="utf-8")

    op = SpeakerProfileOperationV1(
        operation_id=op_id,
        operation_idempotency_key=str(uuid4()),
        op_type="update_profile",
        phase="needs_repair",
        plan=OperationPlanV1(
            actions=[
                OperationPlanActionV1(
                    action="write",
                    path="profiles/missing.speaker_profile.json",
                    expected_before_sha256=None,
                    after_sha256="a" * 64,
                    staging_relpath=f"operations/{op_id}/staging/profiles/x.json",
                )
            ]
        ),
    )
    write_operation(op, root=svc.root)
    assert retention_allows_cleanup(op) is False
    assert staging.exists()
    assert backup.exists()


@pytest.mark.unit
def test_proven_abort_unblocks_and_allows_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, _ = _svc(tmp_path, monkeypatch)
    op_id = str(uuid4())
    idem = str(uuid4())
    # Never-applied prepared op touching a new profile path.
    rel = f"profiles/{uuid4()}.speaker_profile.json"
    op = SpeakerProfileOperationV1(
        operation_id=op_id,
        operation_idempotency_key=idem,
        op_type="create_profile_and_link",
        phase="prepared",
        plan=OperationPlanV1(
            actions=[
                OperationPlanActionV1(
                    action="write",
                    path=rel,
                    expected_before_sha256=None,
                    after_sha256="b" * 64,
                    staging_relpath=f"operations/{op_id}/staging/{rel}",
                )
            ]
        ),
    )
    write_operation(op, root=svc.root)
    report = recover_operation(svc.root, op_id)
    assert report.recovery_class == "proven_aborted"
    assert report.blocking is False

    # Same idempotency key may start a real mutation now.
    result = svc.create_profile_and_link(
        operation_idempotency_key=idem,
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    assert result.outcome.replayed is False
    assert svc.get_profile(result.profile_id) is not None


@pytest.mark.unit
def test_state_dir_loss_preserves_portable_ops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, state_dir = _svc(tmp_path, monkeypatch)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    # Wipe project lock / state_dir — ops live under speaker_profiles.
    shutil.rmtree(state_dir)
    state_dir.mkdir()
    resolver = ManagedTranscriptResolver(
        transcripts_dir=tmp_path / "transcripts",
        discovery_root=tmp_path / "transcripts",
    )
    svc2 = SpeakerProfileService(
        root=svc.root, state_dir=state_dir, resolver=resolver
    )
    assert svc2.get_profile(created.profile_id).display_name == "Alice"
    link = svc2.get_live_link(link_file_key(IMPORT_A, "SPEAKER_00"))
    assert link is not None
    # Receipt still on disk
    op = json.loads(
        operation_path(created.outcome.operation_id, root=svc.root).read_text(
            encoding="utf-8"
        )
    )
    assert op["phase"] == "complete"
    assert op["receipt"]["profile_id"] == created.profile_id


@pytest.mark.unit
def test_crash_safe_unlink_delete_classification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, _ = _svc(tmp_path, monkeypatch)
    svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    key = link_file_key(IMPORT_A, "SPEAKER_00")
    live = link_path(key, root=svc.root)
    before = sha256_file(live)
    op_id = str(uuid4())
    backup_rel = f"operations/{op_id}/backup/{relative_link_path(key)}"
    backup_path = svc.root / backup_rel
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    data = live.read_bytes()
    write_bytes_under_root(backup_path, data, root=svc.root)
    live.unlink()
    from transcriptx.core.speaker_profiles.store_io import fsync_parent

    fsync_parent(live)

    op = SpeakerProfileOperationV1(
        operation_id=op_id,
        operation_idempotency_key=str(uuid4()),
        op_type="unlink",
        phase="staged",
        plan=OperationPlanV1(
            actions=[
                OperationPlanActionV1(
                    action="delete",
                    path=relative_link_path(key),
                    expected_before_sha256=before,
                    after_sha256=None,
                    backup_relpath=backup_rel,
                )
            ]
        ),
    )
    report = classify_operation(svc.root, op)
    assert report.classifications[0].state == "absent"
    assert sha256_file(backup_path) == before
    # Mark failed without proven abort → still blocking
    failed = op.model_copy(
        update={"phase": "failed", "receipt": {"abort_class": "ambiguous"}}
    )
    write_operation(failed, root=svc.root)
    assert classify_operation(svc.root, failed).blocking is True
    # Explicit proven abort receipt unblocks only when never-applied OR after
    # rollback; here delete applied so recovery_class is partial, not proven.
    assert classify_operation(svc.root, failed).recovery_class == "partial"
