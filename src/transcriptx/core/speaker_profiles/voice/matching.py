"""Open-set speaker match scoring and suggestion cache helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np

from transcriptx.core.speaker_profiles.voice.thresholds import (
    PROVISIONAL_THRESHOLDS,
    ThresholdPolicyV1,
    confidence_category,
)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


def aggregate_profile_score(
    query_vectors: list[np.ndarray],
    ref_vectors: list[np.ndarray],
    *,
    policy: ThresholdPolicyV1 | None = None,
) -> float:
    """Mean of top-k ref similarities per query excerpt, then mean across queries."""
    p = policy or PROVISIONAL_THRESHOLDS
    if not query_vectors or not ref_vectors:
        return 0.0
    per_query: list[float] = []
    for q in query_vectors:
        sims = sorted(
            (cosine_similarity(q, r) for r in ref_vectors),
            reverse=True,
        )
        top = sims[: p.top_k_refs_per_query]
        per_query.append(sum(top) / len(top))
    return sum(per_query) / len(per_query)


@dataclass(frozen=True)
class RankedCandidate:
    profile_id: str
    score: float
    confidence: str
    reference_count: int


@dataclass(frozen=True)
class MatchOutcome:
    outcome: str  # SuggestionAvailable | NoReliableMatch
    candidates: tuple[RankedCandidate, ...]
    threshold_policy_id: str
    one_excerpt_fallback: bool


def rank_open_set(
    *,
    query_vectors: list[np.ndarray],
    profile_refs: dict[str, list[np.ndarray]],
    one_excerpt_fallback: bool = False,
    policy: ThresholdPolicyV1 | None = None,
) -> MatchOutcome:
    p = policy or PROVISIONAL_THRESHOLDS
    scored: list[RankedCandidate] = []
    for profile_id, refs in profile_refs.items():
        score = aggregate_profile_score(query_vectors, refs, policy=p)
        scored.append(
            RankedCandidate(
                profile_id=profile_id,
                score=score,
                confidence=confidence_category(score, policy=p),
                reference_count=len(refs),
            )
        )
    scored.sort(key=lambda c: (-c.score, c.profile_id))
    if not scored or scored[0].score < p.tau_no_match:
        return MatchOutcome(
            outcome="NoReliableMatch",
            candidates=(),
            threshold_policy_id=p.policy_id,
            one_excerpt_fallback=one_excerpt_fallback,
        )
    accepted: list[RankedCandidate] = []
    best = scored[0]
    for cand in scored:
        if len(accepted) >= p.max_candidates:
            break
        if cand.score < p.tau_candidate:
            break
        if accepted and (best.score - cand.score) < 0:
            break
        if len(accepted) >= 1 and (best.score - cand.score) < p.margin:
            # Keep if within margin only for second place documentation —
            # require margin against best for additional candidates.
            if (
                cand.profile_id != best.profile_id
                and (best.score - cand.score) < p.margin
            ):
                continue
        # Cap confidence when only one query excerpt
        conf = cand.confidence
        if one_excerpt_fallback and conf == "strong":
            conf = "possible"
        accepted.append(
            RankedCandidate(
                profile_id=cand.profile_id,
                score=cand.score,
                confidence=conf,
                reference_count=cand.reference_count,
            )
        )
    if not accepted:
        return MatchOutcome(
            outcome="NoReliableMatch",
            candidates=(),
            threshold_policy_id=p.policy_id,
            one_excerpt_fallback=one_excerpt_fallback,
        )
    return MatchOutcome(
        outcome="SuggestionAvailable",
        candidates=tuple(accepted),
        threshold_policy_id=p.policy_id,
        one_excerpt_fallback=one_excerpt_fallback,
    )


def reference_corpus_digest(embedding_ids: list[str]) -> str:
    payload = json.dumps(sorted(embedding_ids), separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def suggestion_digest(
    *,
    occurrence_fingerprint: str,
    model_generation_id: str,
    threshold_policy_id: str,
    corpus_digest: str,
    candidate_profile_ids: list[str],
) -> str:
    payload = json.dumps(
        [
            "voice_suggestion_digest.v1",
            occurrence_fingerprint,
            model_generation_id,
            threshold_policy_id,
            corpus_digest,
            candidate_profile_ids,
        ],
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
