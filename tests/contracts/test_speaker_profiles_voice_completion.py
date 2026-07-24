"""Completion tests: wipe, promote, merge transfer, suggestion cache."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest

from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.store_io import profile_content_sha256
from transcriptx.core.speaker_profiles.voice.caches import (
    VoiceSuggestionCache,
    suggestion_cache_key,
)
from transcriptx.core.speaker_profiles.voice.evidence import (
    EnrolExcerptInput,
    VoiceEvidenceService,
)
from transcriptx.core.speaker_profiles.voice.merge_transfer import (
    plan_voice_transfer_on_merge,
)
from transcriptx.core.speaker_profiles.voice.promote import VoicePromotionService
from transcriptx.core.speaker_profiles.voice.wipe import VoiceWipeService
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


def test_wipe_until_complete_removes_samples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, profiles = _svc(tmp_path, monkeypatch)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    evidence = VoiceEvidenceService(root=profiles, state_dir=tmp_path / "state")
    key = link_file_key(IMPORT_A, "SPEAKER_00")
    evidence.enrol_trusted_excerpts_from_link(
        operation_idempotency_key=str(uuid4()),
        link_file_key_value=key,
        excerpts=[
            EnrolExcerptInput(
                clip_start_us=0,
                clip_end_us=1_500_000,
                audio_stat_fingerprint="fastsha256:1:2",
                audio_content_sha256="sha256:y",
                vector=np.ones(192, dtype=np.float32),
                runtime_metadata={},
                model_id="m",
                model_revision="r",
                model_generation_id="g",
            )
        ],
        require_activation=False,
    )
    assert any((profiles / "voice" / "samples").glob("*.json"))
    wipe = VoiceWipeService(root=profiles, state_dir=tmp_path / "state")
    progress = wipe.wipe_until_complete(base_idempotency_key=str(uuid4()))
    assert progress.complete is True
    assert not list((profiles / "voice" / "samples").glob("*.json"))
    # Profile link preserved
    assert svc.get_profile(created.profile_id) is not None
    assert svc.get_live_link(key) is not None


def test_promote_sample(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc, profiles = _svc(tmp_path, monkeypatch)
    from transcriptx.core.speaker_profiles.provenance import LinkProvenanceV1

    svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
        provenance=LinkProvenanceV1(
            link_method="suggestion_assisted",
            suggestion_id="s",
            suggestion_digest="d",
        ),
    )
    evidence = VoiceEvidenceService(root=profiles, state_dir=tmp_path / "state")
    key = link_file_key(IMPORT_A, "SPEAKER_00")
    result = evidence.enrol_trusted_excerpts_from_link(
        operation_idempotency_key=str(uuid4()),
        link_file_key_value=key,
        excerpts=[
            EnrolExcerptInput(
                clip_start_us=0,
                clip_end_us=2_000_000,
                audio_stat_fingerprint="fastsha256:1:2",
                audio_content_sha256="sha256:z",
                vector=np.ones(192, dtype=np.float32),
                runtime_metadata={},
                model_id="m",
                model_revision="r",
                model_generation_id="g",
            )
        ],
        require_activation=False,
    )
    sample_id = result.sample_ids[0]
    sample = json.loads(
        (profiles / "voice" / "samples" / f"{sample_id}.voice_sample.json").read_text()
    )
    assert sample["eligibility_state"] == "ineligible_trust"
    promo = VoicePromotionService(root=profiles, state_dir=tmp_path / "state")
    promo.promote_sample(
        operation_idempotency_key=str(uuid4()),
        sample_id=sample_id,
        require_activation=False,
    )
    sample2 = json.loads(
        (profiles / "voice" / "samples" / f"{sample_id}.voice_sample.json").read_text()
    )
    assert sample2["trust_level"] == "promoted"
    assert sample2["eligibility_state"] == "eligible"


def test_merge_transfers_voice_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, profiles = _svc(tmp_path, monkeypatch)
    a = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    b = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Bob",
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_00",
    )
    evidence = VoiceEvidenceService(root=profiles, state_dir=tmp_path / "state")
    evidence.enrol_trusted_excerpts_from_link(
        operation_idempotency_key=str(uuid4()),
        link_file_key_value=link_file_key(IMPORT_A, "SPEAKER_00"),
        excerpts=[
            EnrolExcerptInput(
                clip_start_us=0,
                clip_end_us=1_500_000,
                audio_stat_fingerprint="fastsha256:1:2",
                audio_content_sha256="sha256:y",
                vector=np.ones(192, dtype=np.float32),
                runtime_metadata={},
                model_id="m",
                model_revision="r",
                model_generation_id="g",
            )
        ],
        require_activation=False,
    )
    VoiceSuggestionCache(profiles).write(
        suggestion_cache_key(
            occurrence_fingerprint="x",
            model_generation_id="g",
            threshold_policy_id="t",
            reference_corpus_digest="sha256:1",
        ),
        {"outcome": "SuggestionAvailable"},
    )
    svc.merge_profiles(
        operation_idempotency_key=str(uuid4()),
        source_profile_id=a.profile_id,
        target_profile_id=b.profile_id,
        expected_source_sha256=profile_content_sha256(a.profile_id, root=profiles),
    )
    samples = list((profiles / "voice" / "samples").glob("*.json"))
    assert samples
    payload = json.loads(samples[0].read_text())
    assert payload["profile_id"] == b.profile_id
    assert payload["ownership_provenance"].get("merged_from_profile_id") == a.profile_id


def test_plan_voice_transfer_empty_when_no_voice(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    root.mkdir()
    w, d = plan_voice_transfer_on_merge(
        root=root, source_profile_id="a", target_profile_id="b"
    )
    assert w == [] and d == []
