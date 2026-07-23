"""Fixture smoke for voice eval harness pair metrics."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from transcriptx.core.speaker_profiles.store_io import dumps_model, utc_now_iso
from transcriptx.core.speaker_profiles.voice.eval_metrics import (
    EligibleEmbeddingRef,
    build_held_out_pairs,
    evaluate_pairs,
    evaluate_speaker_profiles_root,
    write_eval_report,
)
from transcriptx.core.speaker_profiles.voice.models import VoiceEmbeddingV1, VoiceSampleV1
from transcriptx.core.speaker_profiles.voice.runtime import (
    EMBEDDING_DIM,
    MODEL_ID,
    MODEL_REVISION_PIN,
)
from transcriptx.core.speaker_profiles.voice.thresholds import PROVISIONAL_THRESHOLDS
from transcriptx.core.speaker_profiles.voice.vectors import encode_vector_npy_bytes
from transcriptx.core.speaker_profiles.voice.versioning import (
    EMBEDDING_SCHEMA_VERSION,
    PREPROCESSING_POLICY_ID,
    QUALITY_POLICY_ID,
)


def _unit(i: int) -> np.ndarray:
    v = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    v[i % EMBEDDING_DIM] = 1.0
    return v


def test_build_held_out_pairs_no_profile_leakage() -> None:
    refs = [
        EligibleEmbeddingRef("e1", "p1", "s1", "t1", _unit(0)),
        EligibleEmbeddingRef("e2", "p1", "s2", "t2", _unit(0)),
        EligibleEmbeddingRef("e3", "p2", "s3", "t1", _unit(1)),
        EligibleEmbeddingRef("e4", "p2", "s4", "t3", _unit(1)),
    ]
    pairs = build_held_out_pairs(refs, max_same_pairs=10, max_different_pairs=20)
    same = [p for p in pairs if p.kind == "same"]
    different = [p for p in pairs if p.kind == "different"]
    assert same
    assert different
    assert all(p.profile_a == p.profile_b for p in same)
    assert all(p.profile_a != p.profile_b for p in different)
    # Same-speaker pairs prefer cross-transcript when available.
    assert any(p.transcript_a != p.transcript_b for p in same)


def test_evaluate_pairs_empty_reports_none_rates() -> None:
    report = evaluate_pairs(
        [],
        profiles_with_eligible_embeddings=0,
        eligible_embedding_count=0,
    )
    assert report.same_pair_count == 0
    assert report.different_pair_count == 0
    assert report.far_at_tau_candidate is None
    assert report.frr_at_tau_candidate is None
    assert report.same_band_counts["below_candidate"] == 0


def test_evaluate_pairs_reports_far_frr_against_provisional() -> None:
    refs = [
        EligibleEmbeddingRef("e1", "p1", "s1", "t1", _unit(0)),
        EligibleEmbeddingRef("e2", "p1", "s2", "t2", _unit(0)),
        EligibleEmbeddingRef("e3", "p2", "s3", "t1", _unit(5)),
        EligibleEmbeddingRef("e4", "p2", "s4", "t3", _unit(5)),
    ]
    pairs = build_held_out_pairs(refs)
    report = evaluate_pairs(
        pairs,
        profiles_with_eligible_embeddings=2,
        eligible_embedding_count=4,
    )
    assert report.threshold_policy_id == PROVISIONAL_THRESHOLDS.policy_id
    assert report.same_pair_count >= 2
    assert report.different_pair_count >= 1
    assert report.frr_at_tau_candidate == 0.0
    assert report.far_at_tau_candidate == 0.0
    assert report.recommended_action.startswith("Keep voice_threshold.v1")


def test_evaluate_root_and_write_artifact(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    (root / "voice" / "samples").mkdir(parents=True)
    (root / "voice" / "embeddings").mkdir(parents=True)
    (root / "voice" / "vectors").mkdir(parents=True)
    now = utc_now_iso()
    for i, (pid, tid) in enumerate(
        [("p1", "t1"), ("p1", "t2"), ("p2", "t1"), ("p2", "t3")]
    ):
        sample_id = f"sample-{i}"
        embedding_id = f"emb-{i}"
        vec = _unit(0 if pid == "p1" else 3)
        vec_bytes, meta = encode_vector_npy_bytes(vec)
        sample = VoiceSampleV1(
            sample_id=sample_id,
            profile_id=pid,
            source_link_id=f"link-{i}",
            source_link_fingerprint=f"fp-{i}",
            managed_transcript_id=tid,
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
            profile_id=pid,
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
        (root / "voice" / "embeddings" / f"{embedding_id}.voice_embedding.json").write_bytes(
            dumps_model(emb)
        )
        (root / "voice" / "vectors" / f"{embedding_id}.npy").write_bytes(vec_bytes)

    report = evaluate_speaker_profiles_root(root)
    assert report.eligible_embedding_count == 4
    out = tmp_path / "artifacts" / "voice_eval.json"
    write_eval_report(report, out)
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "voice_threshold.v1" in text
    assert "same_scores" not in text
    assert "same_score_summary" in text
