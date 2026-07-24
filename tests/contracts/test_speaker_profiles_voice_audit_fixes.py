"""Audit-gap fixes: generations, backup inventory, accept preconditions, privacy journal."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest

from transcriptx.core.speaker_profiles.errors import StaleConfirmationError
from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.voice.acceptance import (
    AcceptSuggestionRequest,
    VoiceAcceptanceOwner,
)
from transcriptx.core.speaker_profiles.voice.backup_inventory import (
    iter_speaker_profiles_paths_for_backup,
)
from transcriptx.core.speaker_profiles.voice.generations import (
    VoiceGenerationRegistry,
    compute_model_generation_id,
    default_generation_pin,
)
from transcriptx.core.speaker_profiles.voice.privacy_service import VoicePrivacyService
from transcriptx.core.speaker_profiles.voice.runtime import (
    MODEL_ID,
    MODEL_REVISION_PIN,
)
from transcriptx.core.speaker_profiles.voice.vectors import encode_vector_npy_bytes
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


def _write_managed(transcripts_root: Path) -> None:
    originals = transcripts_root / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    archive_rel = "originals/meeting.srt"
    (transcripts_root / archive_rel).write_text("x", encoding="utf-8")
    segs = [
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
        TranscriptMetadata(duration_seconds=2.0, segment_count=2, speaker_count=2),
    )
    path = transcripts_root / "meeting.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    write_initial_sidecar(
        path,
        import_id=IMPORT_A,
        imported_at="2026-01-15T10:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename="meeting.srt",
        archived_original_relpath=archive_rel,
    )


def _svc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[SpeakerProfileService, Path]:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch_roots(monkeypatch, transcripts)
    _write_managed(transcripts)
    profiles = tmp_path / "speaker_profiles"
    state = tmp_path / "state"
    profiles.mkdir()
    state.mkdir()
    resolver = ManagedTranscriptResolver(
        transcripts_dir=transcripts, discovery_root=transcripts
    )
    return (
        SpeakerProfileService(root=profiles, state_dir=state, resolver=resolver),
        profiles,
    )


def test_model_revision_is_pinned_sha() -> None:
    assert MODEL_REVISION_PIN == "0f99f2d0ebe89ac095bcc5903c4dd8f72b367286"
    assert len(MODEL_REVISION_PIN) == 40
    assert MODEL_ID == "speechbrain/spkrec-ecapa-voxceleb"


def test_generation_id_content_addressed_and_activate(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    root.mkdir()
    pin = default_generation_pin()
    again = compute_model_generation_id(
        model_id=pin.model_id,
        model_revision=pin.model_revision,
        speechbrain_pkg=pin.speechbrain_pkg,
        torch_constraint_id=pin.torch_constraint_id,
        preprocessing_policy_id=pin.preprocessing_policy_id,
        embedding_schema_version=pin.embedding_schema_version,
        l2_norm_policy=pin.l2_norm_policy,
    )
    assert pin.model_generation_id == again
    reg = VoiceGenerationRegistry(root)
    activated = reg.ensure_default_generation_and_activate(
        operation_idempotency_key=str(uuid4())
    )
    assert activated.model_generation_id == pin.model_generation_id
    assert reg.read_active() is not None
    assert reg.read_active().model_generation_id == pin.model_generation_id  # type: ignore[union-attr]
    # Idempotent replay
    reg.ensure_default_generation_and_activate(operation_idempotency_key=str(uuid4()))


def test_encode_vector_bytes_no_live_write(tmp_path: Path) -> None:
    data, meta = encode_vector_npy_bytes(np.ones(192, dtype=np.float32))
    assert isinstance(data, (bytes, bytearray))
    assert meta["dimension"] == 192
    assert not any(tmp_path.rglob("*.npy"))


def test_backup_inventory_excludes_voice(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    (root / "profiles").mkdir(parents=True)
    (root / "voice" / "samples").mkdir(parents=True)
    (root / ".cache" / "voice").mkdir(parents=True)
    profile = root / "profiles" / "p.speaker_profile.json"
    sample = root / "voice" / "samples" / "s.voice_sample.json"
    cache = root / ".cache" / "voice" / "x.bin"
    profile.write_text("{}")
    sample.write_text("{}")
    cache.write_text("x")
    kept = iter_speaker_profiles_paths_for_backup(root)
    assert profile in kept
    assert sample not in kept
    assert cache not in kept


def test_privacy_enable_allowed_when_gate_open(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    root.mkdir()
    (tmp_path / "state").mkdir()
    svc = VoicePrivacyService(root=root, state_dir=tmp_path / "state")
    settings = svc.enable(
        operation_idempotency_key=str(uuid4()),
        require_feature_gate=True,
        actor="test",
    )
    assert settings.enabled is True
    assert (root / "voice" / "privacy.voice_settings.json").is_file()


def test_accept_stale_profile_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, profiles = _svc(tmp_path, monkeypatch)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    # Create second profile then archive candidate
    other = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Bob",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_01",
    )
    from transcriptx.core.speaker_profiles.store_io import profile_content_sha256

    svc.archive_profile(
        operation_idempotency_key=str(uuid4()),
        profile_id=other.profile_id,
        expected_content_sha256=profile_content_sha256(other.profile_id, root=profiles),
    )
    owner = VoiceAcceptanceOwner(root=profiles, state_dir=tmp_path / "state")
    link = svc.get_live_link(link_file_key(IMPORT_A, "SPEAKER_00"))
    assert link is not None
    with pytest.raises(StaleConfirmationError):
        owner.accept_suggestion(
            AcceptSuggestionRequest(
                operation_idempotency_key=str(uuid4()),
                managed_transcript_id=IMPORT_A,
                local_speaker_key="SPEAKER_00",
                candidate_profile_id=other.profile_id,
                suggestion_id="s1",
                suggestion_digest="d1",
                confidence_category="possible",
                model_generation_id="g",
                occurrence_fingerprint=link.occurrence_fingerprint,
                expected_link_id=link.link_id,
                expected_owner_profile_id=created.profile_id,
            ),
            require_activation=False,
        )


def test_reject_suggestion_durable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, profiles = _svc(tmp_path, monkeypatch)
    owner = VoiceAcceptanceOwner(root=profiles, state_dir=tmp_path / "state")
    result = owner.reject_suggestion(
        operation_idempotency_key=str(uuid4()),
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
        occurrence_fingerprint="occurrence_fingerprint.v1:x",
        candidate_profile_id="p1",
        suggestion_id="s1",
        suggestion_digest="d1",
        model_generation_id="g",
        reference_corpus_digest="sha256:abc",
        reference_count=2,
        require_activation=False,
    )
    assert result.decision_id is not None
    path = (
        profiles / "voice" / "decisions" / f"{result.decision_id}.voice_decision.json"
    )
    assert path.is_file()
