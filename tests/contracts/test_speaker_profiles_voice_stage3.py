"""Stage 3: voice evidence enrolment, trust, deterministic ids, barrier gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import pytest

from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.provenance import LinkProvenanceV1
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.voice.errors import (
    VoiceFeatureDisabled,
    VoiceFeatureGateClosed,
)
from transcriptx.core.speaker_profiles.voice.evidence import (
    EnrolExcerptInput,
    VoiceEvidenceService,
    eligibility_for_trust,
    trust_from_link_provenance,
)
from transcriptx.core.speaker_profiles.voice.ids import compute_sample_id
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


def _write_managed(transcripts_root: Path) -> Path:
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
        TranscriptMetadata(
            duration_seconds=2.0, segment_count=2, speaker_count=2
        ),
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
    return path


def _svc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[SpeakerProfileService, Path]:
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


def test_trust_mapping() -> None:
    assert trust_from_link_provenance({}) == "manual"
    assert (
        trust_from_link_provenance({"link_method": "suggestion_assisted"})
        == "suggestion_assisted"
    )
    assert (
        trust_from_link_provenance(
            LinkProvenanceV1(
                link_method="suggestion_assisted",
                suggestion_id="s",
                suggestion_digest="d",
            ).to_storage_dict()
        )
        == "suggestion_assisted"
    )
    assert eligibility_for_trust("suggestion_assisted") == "ineligible_trust"
    assert eligibility_for_trust("manual") == "eligible"


def test_enrol_gated_by_activation_barrier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TRANSCRIPTX_VOICE_PRIVACY_DEFAULT_ENABLED", raising=False)
    svc, profiles = _svc(tmp_path, monkeypatch)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    key = link_file_key(IMPORT_A, "SPEAKER_00")
    evidence = VoiceEvidenceService(root=profiles, state_dir=tmp_path / "state")
    vec = np.ones(192, dtype=np.float32)
    excerpt = EnrolExcerptInput(
        clip_start_us=0,
        clip_end_us=1_500_000,
        audio_stat_fingerprint="fastsha256:x",
        audio_content_sha256="sha256:y",
        vector=vec,
        runtime_metadata={"device_class": "cpu"},
        model_id="speechbrain/spkrec-ecapa-voxceleb",
        model_revision="pin",
        model_generation_id="gen-test",
    )
    from transcriptx.core.speaker_profiles.voice.errors import VoiceFeatureDisabled

    # Gate open but privacy default-disabled → processing blocked
    with pytest.raises(VoiceFeatureDisabled):
        evidence.enrol_trusted_excerpts_from_link(
            operation_idempotency_key=str(uuid4()),
            link_file_key_value=key,
            excerpts=[excerpt],
            require_activation=True,
        )
    result = evidence.enrol_trusted_excerpts_from_link(
        operation_idempotency_key=str(uuid4()),
        link_file_key_value=key,
        excerpts=[excerpt],
        require_activation=False,
    )
    assert len(result.sample_ids) == 1
    expected = compute_sample_id(
        occurrence_fingerprint=svc.get_live_link(key).occurrence_fingerprint,  # type: ignore[union-attr]
        audio_content_sha256="sha256:y",
        clip_start_us=0,
        clip_end_us=1_500_000,
        model_generation_id="gen-test",
    )
    assert result.sample_ids[0] == expected
    sample_path = profiles / "voice" / "samples" / f"{expected}.voice_sample.json"
    assert sample_path.is_file()
    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    assert payload["trust_level"] == "manual"
    assert payload["eligibility_state"] == "eligible"
    assert payload["profile_id"] == created.profile_id


def test_enrol_retry_idempotent_same_sample_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, profiles = _svc(tmp_path, monkeypatch)
    svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    key = link_file_key(IMPORT_A, "SPEAKER_00")
    evidence = VoiceEvidenceService(root=profiles, state_dir=tmp_path / "state")
    vec = np.random.default_rng(1).standard_normal(192).astype(np.float32)
    excerpt = EnrolExcerptInput(
        clip_start_us=1000,
        clip_end_us=2_000_000,
        audio_stat_fingerprint="fastsha256:x",
        audio_content_sha256="sha256:z",
        vector=vec,
        runtime_metadata={},
        model_id="m",
        model_revision="r",
        model_generation_id="g",
    )
    op_key = str(uuid4())
    first = evidence.enrol_trusted_excerpts_from_link(
        operation_idempotency_key=op_key,
        link_file_key_value=key,
        excerpts=[excerpt],
        require_activation=False,
    )
    second = evidence.enrol_trusted_excerpts_from_link(
        operation_idempotency_key=op_key,
        link_file_key_value=key,
        excerpts=[excerpt],
        require_activation=False,
    )
    assert second.replayed is True
    assert first.sample_ids == second.sample_ids
