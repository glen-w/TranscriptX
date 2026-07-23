"""Accept co-journals retained query-evidence (suggestion_assisted)."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest

from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.voice.acceptance import (
    AcceptSuggestionRequest,
    VoiceAcceptanceOwner,
)
from transcriptx.core.speaker_profiles.voice.evidence import EnrolExcerptInput
from transcriptx.core.speaker_profiles.voice.models import VoiceSampleV1
from transcriptx.core.speaker_profiles.voice.runtime import (
    EMBEDDING_DIM,
    MODEL_ID,
    MODEL_REVISION_PIN,
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


def _excerpt() -> EnrolExcerptInput:
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec[0] = 1.0
    return EnrolExcerptInput(
        clip_start_us=0,
        clip_end_us=1_000_000,
        audio_stat_fingerprint="stat-a",
        audio_content_sha256="content-a",
        vector=vec,
        runtime_metadata={"source": "test"},
        model_id=MODEL_ID,
        model_revision=MODEL_REVISION_PIN,
        model_generation_id="gen-test",
    )


def test_accept_cojournals_query_evidence_ineligible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, profiles = _svc(tmp_path, monkeypatch)
    alice = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    owner = VoiceAcceptanceOwner(
        root=profiles, state_dir=tmp_path / "state", profile_service=svc
    )
    op_key = str(uuid4())
    result = owner.accept_suggestion(
        AcceptSuggestionRequest(
            operation_idempotency_key=op_key,
            managed_transcript_id=IMPORT_B,
            local_speaker_key="SPEAKER_00",
            candidate_profile_id=alice.profile_id,
            suggestion_id="s1",
            suggestion_digest="d1",
            confidence_category="strong",
            model_generation_id="gen-test",
            occurrence_fingerprint="fp-b",
            query_excerpts=(_excerpt(),),
        ),
        require_activation=False,
    )
    assert result.decision_id is not None
    assert len(result.sample_ids) == 1
    assert len(result.embedding_ids) == 1
    sample_path = (
        profiles / "voice" / "samples" / f"{result.sample_ids[0]}.voice_sample.json"
    )
    assert sample_path.is_file()
    sample = VoiceSampleV1.model_validate_json(sample_path.read_text(encoding="utf-8"))
    assert sample.trust_level == "suggestion_assisted"
    assert sample.eligibility_state == "ineligible_trust"
    assert sample.profile_id == alice.profile_id
    emb_path = (
        profiles
        / "voice"
        / "embeddings"
        / f"{result.embedding_ids[0]}.voice_embedding.json"
    )
    assert emb_path.is_file()
    vec_path = profiles / "voice" / "vectors" / f"{result.embedding_ids[0]}.npy"
    assert vec_path.is_file()
    link = svc.get_live_link(link_file_key(IMPORT_B, "SPEAKER_00"))
    assert link is not None
    assert link.profile_id == alice.profile_id

    # Replay is idempotent — no duplicate samples.
    again = owner.accept_suggestion(
        AcceptSuggestionRequest(
            operation_idempotency_key=op_key,
            managed_transcript_id=IMPORT_B,
            local_speaker_key="SPEAKER_00",
            candidate_profile_id=alice.profile_id,
            suggestion_id="s1",
            suggestion_digest="d1",
            confidence_category="strong",
            model_generation_id="gen-test",
            occurrence_fingerprint="fp-b",
            query_excerpts=(_excerpt(),),
        ),
        require_activation=False,
    )
    assert again.sample_ids == result.sample_ids
    samples = list((profiles / "voice" / "samples").glob("*.voice_sample.json"))
    assert len(samples) == 1


def test_reject_and_leave_unlinked_write_no_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, profiles = _svc(tmp_path, monkeypatch)
    alice = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    owner = VoiceAcceptanceOwner(
        root=profiles, state_dir=tmp_path / "state", profile_service=svc
    )
    owner.reject_suggestion(
        operation_idempotency_key=str(uuid4()),
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_00",
        occurrence_fingerprint="fp-b",
        candidate_profile_id=alice.profile_id,
        suggestion_id="s1",
        suggestion_digest="d1",
        model_generation_id="gen-test",
        reference_corpus_digest="corpus",
        reference_count=1,
        require_activation=False,
    )
    left = owner.leave_unlinked()
    assert left.decision_id is None
    samples_dir = profiles / "voice" / "samples"
    if samples_dir.is_dir():
        assert list(samples_dir.glob("*.voice_sample.json")) == []
