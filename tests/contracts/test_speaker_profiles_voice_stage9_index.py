"""Stage 9 disposable voice reference index."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from transcriptx.core.speaker_profiles.models import SpeakerProfileV1
from transcriptx.core.speaker_profiles.operations import relative_profile_path
from transcriptx.core.speaker_profiles.store_io import dumps_model, utc_now_iso
from transcriptx.core.speaker_profiles.voice.matching import reference_corpus_digest
from transcriptx.core.speaker_profiles.voice.models import (
    VoiceEmbeddingV1,
    VoiceSampleV1,
)
from transcriptx.core.speaker_profiles.voice.ref_index import (
    VoiceRefIndexStore,
    load_or_rebuild_refs,
    measure_scan_vs_index,
    rebuild_ref_index,
)
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


def _seed_profile_and_emb(root: Path, *, profile_id: str, embedding_id: str) -> None:
    (root / "profiles").mkdir(parents=True, exist_ok=True)
    (root / "voice" / "samples").mkdir(parents=True, exist_ok=True)
    (root / "voice" / "embeddings").mkdir(parents=True, exist_ok=True)
    (root / "voice" / "vectors").mkdir(parents=True, exist_ok=True)
    now = utc_now_iso()
    profile = SpeakerProfileV1(
        profile_id=profile_id,
        display_name=profile_id,
        aliases=[],
        notes=None,
        accent_color="#112233",
        status="active",
        merged_into_profile_id=None,
        created_at=now,
        updated_at=now,
    )
    (root / relative_profile_path(profile_id)).write_bytes(dumps_model(profile))
    sample_id = f"sample-{embedding_id}"
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec[0] = 1.0
    vec_bytes, meta = encode_vector_npy_bytes(vec)
    sample = VoiceSampleV1(
        sample_id=sample_id,
        profile_id=profile_id,
        source_link_id="link-1",
        source_link_fingerprint="fp-1",
        managed_transcript_id="t1",
        local_speaker_key="SPEAKER_00",
        occurrence_fingerprint="fp-1",
        audio_stat_fingerprint="stat",
        audio_content_sha256="sha",
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
        source_link_id="link-1",
        source_link_fingerprint="fp-1",
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
    (root / "voice" / "embeddings" / f"{embedding_id}.voice_embedding.json").write_bytes(
        dumps_model(emb)
    )
    (root / "voice" / "vectors" / f"{embedding_id}.npy").write_bytes(vec_bytes)


def test_ref_index_rebuild_and_hit(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    _seed_profile_and_emb(root, profile_id="p1", embedding_id="e1")
    _seed_profile_and_emb(root, profile_id="p2", embedding_id="e2")
    digest = reference_corpus_digest(["e1", "e2"])
    loaded = rebuild_ref_index(
        root, model_generation_id="gen", corpus_digest=digest
    )
    assert loaded is not None
    assert loaded.meta.row_count == 2
    refs, ids, source = load_or_rebuild_refs(
        root, model_generation_id="gen", corpus_digest=digest
    )
    assert source == "index"
    assert set(ids) == {"e1", "e2"}
    assert set(refs.keys()) == {"p1", "p2"}
    store = VoiceRefIndexStore(root)
    assert store.read(model_generation_id="gen", corpus_digest=digest) is not None


def test_ref_index_digest_miss_falls_back(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    _seed_profile_and_emb(root, profile_id="p1", embedding_id="e1")
    refs, ids, source = load_or_rebuild_refs(
        root,
        model_generation_id="gen",
        corpus_digest="sha256:deadbeef",
    )
    assert source in ("index_rebuild", "scan")
    assert ids == ["e1"]
    assert "p1" in refs


def test_measure_scan_vs_index_smoke() -> None:
    report = measure_scan_vs_index(profile_count=50, refs_per_profile=2, seed=1)
    assert report["row_count"] == 100
    assert "full_scan_matmul_ms" in report
    assert report["advisory_full_scan_p95_ms"] == 500


def test_ref_index_store_rejects_corrupt_and_mismatched(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    store = VoiceRefIndexStore(root)
    digest = "sha256:abc"
    matrix = np.zeros((2, EMBEDDING_DIM), dtype=np.float32)
    matrix[0, 0] = 1.0
    matrix[1, 1] = 1.0
    store.write(
        model_generation_id="gen",
        corpus_digest=digest,
        embedding_ids=["e1", "e2"],
        profile_ids=["p1", "p2"],
        matrix=matrix,
    )
    # Shape mismatch on write.
    with pytest.raises(ValueError, match="matrix rows"):
        store.write(
            model_generation_id="gen",
            corpus_digest=digest,
            embedding_ids=["e1"],
            profile_ids=["p1", "p2"],
            matrix=matrix,
        )
    # Corrupt meta → miss.
    meta_path = store.dir_for(model_generation_id="gen", corpus_digest=digest) / "meta.json"
    meta_path.write_text("{not-json", encoding="utf-8")
    assert store.read(model_generation_id="gen", corpus_digest=digest) is None


def test_ref_index_empty_corpus_rebuilds_none(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    root.mkdir()
    assert (
        rebuild_ref_index(
            root, model_generation_id="gen", corpus_digest="sha256:empty"
        )
        is None
    )
    refs, ids, source = load_or_rebuild_refs(
        root, model_generation_id="gen", corpus_digest="sha256:empty"
    )
    assert refs == {}
    assert ids == []
    assert source == "scan"


def test_list_eligible_embedding_ids_respects_link_cap(tmp_path: Path) -> None:
    from transcriptx.core.speaker_profiles.voice.ref_index import (
        list_eligible_embedding_ids,
    )

    root = tmp_path / "speaker_profiles"
    # Same source_link_id for both embeddings → cap of 1 keeps first only.
    _seed_profile_and_emb(root, profile_id="p1", embedding_id="e1")
    _seed_profile_and_emb(root, profile_id="p1", embedding_id="e2")
    ids = list_eligible_embedding_ids(
        root, model_generation_id="gen", max_refs_per_source_link=1
    )
    assert ids == ["e1"]
