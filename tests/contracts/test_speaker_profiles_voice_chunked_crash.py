"""Chunked voice merge transfer + deepened crash recovery matrix."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest

from transcriptx.core.speaker_profiles.operations import OperationEngine
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.store_io import (
    dumps_model,
    profile_content_sha256,
    utc_now_iso,
)
from transcriptx.core.speaker_profiles.voice.acceptance import (
    AcceptSuggestionRequest,
    VoiceAcceptanceOwner,
)
from transcriptx.core.speaker_profiles.voice.caches import VoiceSuggestionCache
from transcriptx.core.speaker_profiles.voice.evidence import EnrolExcerptInput
from transcriptx.core.speaker_profiles.voice.merge_transfer import (
    apply_chunked_voice_transfer,
    chunk_planned_writes,
    plan_voice_transfer_on_merge,
    voice_chunk_idempotency_key,
)
from transcriptx.core.speaker_profiles.voice.models import (
    VoiceEmbeddingV1,
    VoiceSampleV1,
)
from transcriptx.core.speaker_profiles.voice.promote import VoicePromotionService
from transcriptx.core.speaker_profiles.voice.runtime import (
    EMBEDDING_DIM,
    MODEL_ID,
    MODEL_REVISION_PIN,
)
from transcriptx.core.speaker_profiles.voice.vectors import encode_vector_npy_bytes
from transcriptx.core.speaker_profiles.voice.versioning import (
    EMBEDDING_SCHEMA_VERSION,
    PREPROCESSING_POLICY_ID,
    QUALITY_POLICY_ID,
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


def _seed_voice_rows(root: Path, *, profile_id: str, n: int) -> list[str]:
    (root / "voice" / "samples").mkdir(parents=True, exist_ok=True)
    (root / "voice" / "embeddings").mkdir(parents=True, exist_ok=True)
    (root / "voice" / "vectors").mkdir(parents=True, exist_ok=True)
    now = utc_now_iso()
    sample_ids: list[str] = []
    for i in range(n):
        sample_id = f"sample-{profile_id[:8]}-{i}"
        embedding_id = f"emb-{profile_id[:8]}-{i}"
        vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        vec[i % EMBEDDING_DIM] = 1.0
        vec_bytes, meta = encode_vector_npy_bytes(vec)
        sample = VoiceSampleV1(
            sample_id=sample_id,
            profile_id=profile_id,
            source_link_id=f"link-{i}",
            source_link_fingerprint=f"fp-{i}",
            managed_transcript_id=IMPORT_A,
            local_speaker_key="SPEAKER_00",
            occurrence_fingerprint=f"fp-{i}",
            audio_stat_fingerprint="stat",
            audio_content_sha256=f"sha-{i}",
            clip_start_us=0,
            clip_end_us=1_000_000,
            model_generation_id="gen",
            preprocessing_policy_id=PREPROCESSING_POLICY_ID,
            quality_policy_id=QUALITY_POLICY_ID,
            trust_level="manual",
            eligibility_state="eligible",
            created_at=now,
        )
        emb = VoiceEmbeddingV1(
            embedding_id=embedding_id,
            sample_id=sample_id,
            profile_id=profile_id,
            source_link_id=f"link-{i}",
            source_link_fingerprint=f"fp-{i}",
            embedding_schema_version=EMBEDDING_SCHEMA_VERSION,
            model_id=MODEL_ID,
            model_revision=MODEL_REVISION_PIN,
            model_generation_id="gen",
            preprocessing_policy_id=PREPROCESSING_POLICY_ID,
            quality_policy_id=QUALITY_POLICY_ID,
            trust_level="manual",
            eligibility_state="eligible",
            vector_sha256=str(meta["vector_sha256"]),
            nbytes=int(meta["nbytes"]),
            dimension=int(meta["dimension"]),
            created_at=now,
        )
        (root / "voice" / "samples" / f"{sample_id}.voice_sample.json").write_bytes(
            dumps_model(sample)
        )
        (
            root / "voice" / "embeddings" / f"{embedding_id}.voice_embedding.json"
        ).write_bytes(dumps_model(emb))
        (root / "voice" / "vectors" / f"{embedding_id}.npy").write_bytes(vec_bytes)
        sample_ids.append(sample_id)
    return sample_ids


def test_chunk_planned_writes_splits() -> None:
    writes, _ = plan_voice_transfer_on_merge(
        root=Path("/nonexistent"),
        source_profile_id="x",
        target_profile_id="y",
    )
    assert chunk_planned_writes(writes, chunk_size=4) == []
    fake = [object()] * 10  # type: ignore[list-item]
    chunks = chunk_planned_writes(fake, chunk_size=4)  # type: ignore[arg-type]
    assert [len(c) for c in chunks] == [4, 4, 2]


def test_merge_profiles_chunked_voice_transfer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, profiles = _svc(tmp_path, monkeypatch)
    source = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Source",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    target = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Target",
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_00",
    )
    _seed_voice_rows(profiles, profile_id=source.profile_id, n=5)
    sha = profile_content_sha256(source.profile_id, root=profiles)
    assert sha is not None
    result = svc.merge_profiles(
        operation_idempotency_key=str(uuid4()),
        source_profile_id=source.profile_id,
        target_profile_id=target.profile_id,
        expected_source_sha256=sha,
    )
    assert result.outcome.receipt.get("voice_chunks_total", 0) >= 1
    for path in (profiles / "voice" / "samples").glob("*.voice_sample.json"):
        sample = VoiceSampleV1.model_validate_json(path.read_text(encoding="utf-8"))
        assert sample.profile_id == target.profile_id


def test_chunked_transfer_resumes_after_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, profiles = _svc(tmp_path, monkeypatch)
    source = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Source",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    target = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Target",
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_00",
    )
    _seed_voice_rows(profiles, profile_id=source.profile_id, n=6)
    engine = OperationEngine(profiles)
    base_key = str(uuid4())
    # Complete only the first full-plan chunk, then resume remaining source rows.
    writes, _ = plan_voice_transfer_on_merge(
        root=profiles,
        source_profile_id=source.profile_id,
        target_profile_id=target.profile_id,
    )
    chunks = chunk_planned_writes(writes, chunk_size=4)
    assert len(chunks) >= 2
    engine.run(
        op_type="voice_merge_transfer_chunk",
        operation_idempotency_key=voice_chunk_idempotency_key(base_key, 0, chunks[0]),
        writes=chunks[0],
        deletes=[],
        receipt_extra={"chunk_index": 0},
    )
    receipt = apply_chunked_voice_transfer(
        root=profiles,
        engine=engine,
        operation_idempotency_key=base_key,
        source_profile_id=source.profile_id,
        target_profile_id=target.profile_id,
        chunk_size=4,
    )
    # Remaining plan is a new chunk set; prior chunk-0 key does not collide.
    assert receipt.chunks_complete == receipt.chunks_total
    for path in (profiles / "voice" / "samples").glob("*.voice_sample.json"):
        sample = VoiceSampleV1.model_validate_json(path.read_text(encoding="utf-8"))
        assert sample.profile_id == target.profile_id


def test_accept_with_query_evidence_replay_after_complete(
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
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec[0] = 1.0
    excerpt = EnrolExcerptInput(
        clip_start_us=0,
        clip_end_us=1_000_000,
        audio_stat_fingerprint="stat",
        audio_content_sha256="content",
        vector=vec,
        runtime_metadata={},
        model_id=MODEL_ID,
        model_revision=MODEL_REVISION_PIN,
        model_generation_id="gen",
    )
    op_key = str(uuid4())
    first = owner.accept_suggestion(
        AcceptSuggestionRequest(
            operation_idempotency_key=op_key,
            managed_transcript_id=IMPORT_B,
            local_speaker_key="SPEAKER_00",
            candidate_profile_id=alice.profile_id,
            suggestion_id="s1",
            suggestion_digest="d1",
            confidence_category="strong",
            model_generation_id="gen",
            occurrence_fingerprint="fp",
            query_excerpts=(excerpt,),
        ),
        require_activation=False,
    )
    assert first.sample_ids
    second = owner.accept_suggestion(
        AcceptSuggestionRequest(
            operation_idempotency_key=op_key,
            managed_transcript_id=IMPORT_B,
            local_speaker_key="SPEAKER_00",
            candidate_profile_id=alice.profile_id,
            suggestion_id="s1",
            suggestion_digest="d1",
            confidence_category="strong",
            model_generation_id="gen",
            occurrence_fingerprint="fp",
            query_excerpts=(excerpt,),
        ),
        require_activation=False,
    )
    assert second.sample_ids == first.sample_ids
    assert len(list((profiles / "voice" / "samples").glob("*.json"))) == 1


def test_promote_idempotent_and_suggestion_digest_stale_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, profiles = _svc(tmp_path, monkeypatch)
    alice = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    sample_ids = _seed_voice_rows(profiles, profile_id=alice.profile_id, n=1)
    # Force suggestion_assisted / ineligible so promote has work.
    sample_path = profiles / "voice" / "samples" / f"{sample_ids[0]}.voice_sample.json"
    sample = VoiceSampleV1.model_validate_json(sample_path.read_text(encoding="utf-8"))
    sample = sample.model_copy(
        update={
            "trust_level": "suggestion_assisted",
            "eligibility_state": "ineligible_trust",
        }
    )
    sample_path.write_bytes(dumps_model(sample))
    emb_path = next((profiles / "voice" / "embeddings").glob("*.voice_embedding.json"))
    emb = VoiceEmbeddingV1.model_validate_json(emb_path.read_text(encoding="utf-8"))
    emb = emb.model_copy(
        update={
            "trust_level": "suggestion_assisted",
            "eligibility_state": "ineligible_trust",
        }
    )
    emb_path.write_bytes(dumps_model(emb))

    promote = VoicePromotionService(root=profiles, state_dir=tmp_path / "state")
    op_key = str(uuid4())
    first = promote.promote_sample(
        operation_idempotency_key=op_key,
        sample_id=sample_ids[0],
        require_activation=False,
    )
    again = promote.promote_sample(
        operation_idempotency_key=op_key,
        sample_id=sample_ids[0],
        require_activation=False,
    )
    assert again == first
    assert first  # decision id recorded

    cache = VoiceSuggestionCache(profiles)
    cache.write(
        "deadbeef" * 8,
        {
            "schema_id": "transcriptx.voice_match_suggestion.v1",
            "suggestion_digest": "old",
            "reference_corpus_digest": "stale",
            "outcome": "SuggestionAvailable",
            "candidates_ui": [],
        },
    )
    assert cache.read("deadbeef" * 8) is not None
    cache.invalidate_all()
    assert cache.read("deadbeef" * 8) is None
