"""Contracts for trusted-voice persistence: inventory, profile wipe, layout."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest

from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.voice.evidence import (
    EnrolExcerptInput,
    VoiceEvidenceService,
)
from transcriptx.core.speaker_profiles.voice.export_exclude import (
    is_voice_excluded_relpath,
)
from transcriptx.core.speaker_profiles.voice.inventory import list_samples_for_profile
from transcriptx.core.speaker_profiles.voice.privacy import VoicePrivacyStore
from transcriptx.core.speaker_profiles.voice.wipe import (
    VoiceWipeService,
    list_voice_paths_for_profile,
)
from transcriptx.io.import_metadata_sidecar import write_initial_sidecar
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    create_transcript_document,
)

IMPORT_A = "550e8400-e29b-41d4-a716-446655440000"
IMPORT_B = "660e8400-e29b-41d4-a716-446655440001"


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


def _write_managed(transcripts_root: Path, *, name: str, import_id: str) -> None:
    originals = transcripts_root / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    archive_rel = f"originals/{name}.srt"
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


def _svc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[SpeakerProfileService, Path]:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch_roots(monkeypatch, transcripts)
    _write_managed(transcripts, name="meeting", import_id=IMPORT_A)
    _write_managed(transcripts, name="other", import_id=IMPORT_B)
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


def _enrol(
    profiles: Path,
    state: Path,
    *,
    link_key: str,
    fingerprint: str,
    clip_start_us: int = 0,
    clip_end_us: int = 1_500_000,
) -> tuple[str, ...]:
    evidence = VoiceEvidenceService(root=profiles, state_dir=state)
    result = evidence.enrol_trusted_excerpts_from_link(
        operation_idempotency_key=str(uuid4()),
        link_file_key_value=link_key,
        excerpts=[
            EnrolExcerptInput(
                clip_start_us=clip_start_us,
                clip_end_us=clip_end_us,
                audio_stat_fingerprint=fingerprint,
                audio_content_sha256=f"sha256:{fingerprint}",
                vector=np.ones(192, dtype=np.float32),
                runtime_metadata={},
                model_id="m",
                model_revision="r",
                model_generation_id="g",
            )
        ],
        require_activation=False,
    )
    return result.sample_ids


@pytest.mark.contract
def test_list_samples_for_profile_filters_and_skips_corrupt(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    samples = root / "voice" / "samples"
    samples.mkdir(parents=True)
    good = {
        "sample_id": "abc",
        "profile_id": "p1",
        "trust_level": "manual",
        "eligibility_state": "eligible",
        "managed_transcript_id": IMPORT_A,
        "local_speaker_key": "SPEAKER_00",
    }
    (samples / "abc.voice_sample.json").write_text(json.dumps(good), encoding="utf-8")
    (samples / "other.voice_sample.json").write_text(
        json.dumps({**good, "sample_id": "other", "profile_id": "p2"}),
        encoding="utf-8",
    )
    (samples / "bad.voice_sample.json").write_text("{not-json", encoding="utf-8")

    listed = list_samples_for_profile("p1", root=root)
    assert len(listed) == 1
    assert listed[0].sample_id == "abc"
    assert listed[0].eligibility_state == "eligible"
    assert list_samples_for_profile("missing", root=root) == []
    assert list_samples_for_profile("p1", root=tmp_path / "empty") == []


@pytest.mark.contract
def test_export_exclude_normalizes_relative_prefixes() -> None:
    assert is_voice_excluded_relpath("voice")
    assert is_voice_excluded_relpath("./voice/samples/x.json")
    assert is_voice_excluded_relpath(".cache/voice/indexes/i.bin")
    assert not is_voice_excluded_relpath("profiles/p.speaker_profile.json")
    assert not is_voice_excluded_relpath("operations/op.json")


@pytest.mark.contract
def test_wipe_profile_voice_leaves_other_profile_and_privacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, profiles = _svc(tmp_path, monkeypatch)
    state = tmp_path / "state"
    alice = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    bob = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Bob",
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_00",
    )
    alice_samples = _enrol(
        profiles,
        state,
        link_key=link_file_key(IMPORT_A, "SPEAKER_00"),
        fingerprint="fastsha256:alice",
        clip_start_us=0,
        clip_end_us=1_500_000,
    )
    bob_samples = _enrol(
        profiles,
        state,
        link_key=link_file_key(IMPORT_B, "SPEAKER_00"),
        fingerprint="fastsha256:bob",
        clip_start_us=2_000_000,
        clip_end_us=3_500_000,
    )
    assert alice_samples and bob_samples
    assert set(alice_samples).isdisjoint(bob_samples)

    VoicePrivacyStore(profiles).enable(actor="test")
    privacy_path = profiles / "voice" / "privacy.voice_settings.json"
    assert privacy_path.is_file()

    alice_paths = list_voice_paths_for_profile(profiles, alice.profile_id)
    assert alice_paths
    assert all("voice/" in p for p in alice_paths)

    wipe = VoiceWipeService(root=profiles, state_dir=state)
    progress = wipe.wipe_profile_voice(
        operation_idempotency_key=str(uuid4()),
        profile_id=alice.profile_id,
    )
    assert progress.complete is True
    assert progress.deleted >= 1

    assert list_samples_for_profile(alice.profile_id, root=profiles) == []
    bob_listed = list_samples_for_profile(bob.profile_id, root=profiles)
    assert len(bob_listed) == 1
    assert bob_listed[0].sample_id == bob_samples[0]
    assert privacy_path.is_file()
    assert VoicePrivacyStore(profiles).read().enabled is True
    assert svc.get_live_link(link_file_key(IMPORT_A, "SPEAKER_00")) is not None
    assert svc.get_live_link(link_file_key(IMPORT_B, "SPEAKER_00")) is not None


@pytest.mark.contract
def test_wipe_profile_voice_noop_when_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, profiles = _svc(tmp_path, monkeypatch)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    wipe = VoiceWipeService(root=profiles, state_dir=tmp_path / "state")
    progress = wipe.wipe_profile_voice(
        operation_idempotency_key=str(uuid4()),
        profile_id=created.profile_id,
    )
    assert progress.complete is True
    assert progress.deleted == 0
    assert progress.chunk_operation_id is None
