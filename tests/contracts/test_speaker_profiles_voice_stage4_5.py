"""Stage 4–5: aggregation, open-set rejection, decision suppression."""

from __future__ import annotations

import numpy as np

from transcriptx.core.speaker_profiles.voice.decisions import (
    decision_suppresses_suggestion,
)
from transcriptx.core.speaker_profiles.voice.matching import (
    aggregate_profile_score,
    rank_open_set,
    reference_corpus_digest,
)
from transcriptx.core.speaker_profiles.voice.models import VoiceMatchDecisionV1
from transcriptx.core.speaker_profiles.voice.thresholds import ThresholdPolicyV1


def _unit(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(192).astype(np.float32)
    return v / np.linalg.norm(v)


def test_no_match_suppresses_weak_nearest() -> None:
    q = [_unit(1)]
    refs = {"p1": [_unit(99)]}  # unrelated → low score
    policy = ThresholdPolicyV1(tau_no_match=0.99, tau_candidate=0.995)
    out = rank_open_set(query_vectors=q, profile_refs=refs, policy=policy)
    assert out.outcome == "NoReliableMatch"
    assert out.candidates == ()


def test_top_k_ranking() -> None:
    q = [_unit(0)]
    # Make p_good nearly identical to query
    good = q[0].copy()
    other = _unit(50)
    out = rank_open_set(
        query_vectors=q,
        profile_refs={"p_good": [good], "p_other": [other]},
        policy=ThresholdPolicyV1(
            tau_no_match=0.1, tau_candidate=0.1, margin=0.01, strong_min=0.9
        ),
    )
    assert out.outcome == "SuggestionAvailable"
    assert out.candidates[0].profile_id == "p_good"


def test_aggregate_uses_top_k_mean() -> None:
    q = [_unit(2)]
    refs = [_unit(2), _unit(3), _unit(4), _unit(5)]
    # Force identical first ref
    refs[0] = q[0].copy()
    score = aggregate_profile_score(q, refs, policy=ThresholdPolicyV1(top_k_refs_per_query=1))
    assert score > 0.99


def test_reject_suppresses_until_corpus_changes() -> None:
    decision = VoiceMatchDecisionV1(
        decision_id="d1",
        decision_kind="reject",
        scope="occurrence_profile",
        managed_transcript_id="550e8400-e29b-41d4-a716-446655440000",
        local_speaker_key="SPEAKER_00",
        occurrence_fingerprint="occurrence_fingerprint.v1:x",
        candidate_profile_id="p1",
        model_generation_id="gen1",
        reference_corpus_digest="sha256:aaa",
        created_at="2026-01-01T00:00:00Z",
    )
    assert decision_suppresses_suggestion(
        [decision],
        candidate_profile_id="p1",
        model_generation_id="gen1",
        reference_corpus_digest="sha256:aaa",
    )
    assert not decision_suppresses_suggestion(
        [decision],
        candidate_profile_id="p1",
        model_generation_id="gen1",
        reference_corpus_digest="sha256:bbb",
    )


def test_corpus_digest_stable() -> None:
    assert reference_corpus_digest(["b", "a"]) == reference_corpus_digest(["a", "b"])
