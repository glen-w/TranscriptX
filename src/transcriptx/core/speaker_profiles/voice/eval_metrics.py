"""Pair metrics for voice threshold calibration (eval harness).

Does not invent new threshold numbers — reports FAR/FRR and band hit rates
against the current ``ThresholdPolicyV1``. Freeze to a new
``threshold_policy_id`` only after a labeled, held-out library run.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from transcriptx.core.speaker_profiles.voice.matching import cosine_similarity
from transcriptx.core.speaker_profiles.voice.models import (
    VoiceEmbeddingV1,
    VoiceSampleV1,
)
from transcriptx.core.speaker_profiles.voice.thresholds import (
    PROVISIONAL_THRESHOLDS,
    ThresholdPolicyV1,
    confidence_category,
)
from transcriptx.core.speaker_profiles.voice.vectors import load_vector_npy


@dataclass(frozen=True)
class EligibleEmbeddingRef:
    embedding_id: str
    profile_id: str
    sample_id: str
    managed_transcript_id: str
    vector: np.ndarray


@dataclass(frozen=True)
class PairScore:
    kind: str  # same | different
    profile_a: str
    profile_b: str
    transcript_a: str
    transcript_b: str
    embedding_a: str
    embedding_b: str
    score: float


@dataclass(frozen=True)
class EvalReport:
    threshold_policy_id: str
    profiles_with_eligible_embeddings: int
    eligible_embedding_count: int
    same_pair_count: int
    different_pair_count: int
    same_scores: list[float]
    different_scores: list[float]
    far_at_tau_candidate: float | None
    frr_at_tau_candidate: float | None
    far_at_tau_no_match: float | None
    frr_at_tau_no_match: float | None
    same_band_counts: dict[str, int]
    different_band_counts: dict[str, int]
    policy: dict[str, Any]
    note: str
    recommended_action: str

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_eligible_embedding_refs(root: Path) -> list[EligibleEmbeddingRef]:
    """Load eligible manual/promoted embeddings with sample transcript ids."""
    root = Path(root)
    emb_dir = root / "voice" / "embeddings"
    samples_dir = root / "voice" / "samples"
    vectors_dir = root / "voice" / "vectors"
    refs: list[EligibleEmbeddingRef] = []
    if not emb_dir.is_dir():
        return refs
    for path in sorted(emb_dir.glob("*.voice_embedding.json")):
        try:
            emb = VoiceEmbeddingV1.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if emb.eligibility_state != "eligible":
            continue
        if emb.trust_level not in ("manual", "promoted"):
            continue
        sample_path = samples_dir / f"{emb.sample_id}.voice_sample.json"
        if not sample_path.is_file():
            continue
        try:
            sample = VoiceSampleV1.model_validate_json(
                sample_path.read_text(encoding="utf-8")
            )
        except Exception:
            continue
        vec_path = vectors_dir / f"{emb.embedding_id}.npy"
        if not vec_path.is_file():
            continue
        try:
            vector = load_vector_npy(vec_path)
        except Exception:
            continue
        refs.append(
            EligibleEmbeddingRef(
                embedding_id=emb.embedding_id,
                profile_id=emb.profile_id,
                sample_id=emb.sample_id,
                managed_transcript_id=sample.managed_transcript_id,
                vector=vector,
            )
        )
    return refs


def build_held_out_pairs(
    refs: list[EligibleEmbeddingRef],
    *,
    max_same_pairs: int = 5000,
    max_different_pairs: int = 5000,
    seed: int = 0,
) -> list[PairScore]:
    """Build same/different pairs without same-embedding or same-transcript leakage.

    Same pairs prefer different ``managed_transcript_id`` when available.
    Different pairs never share ``profile_id``.
    """
    rng = np.random.default_rng(seed)
    by_profile: dict[str, list[EligibleEmbeddingRef]] = {}
    for ref in refs:
        by_profile.setdefault(ref.profile_id, []).append(ref)

    pairs: list[PairScore] = []

    # Same-speaker pairs
    same_candidates: list[tuple[EligibleEmbeddingRef, EligibleEmbeddingRef]] = []
    for group in by_profile.values():
        if len(group) < 2:
            continue
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                if a.embedding_id == b.embedding_id:
                    continue
                same_candidates.append((a, b))
    # Prefer cross-transcript same pairs first
    same_candidates.sort(
        key=lambda ab: (
            0 if ab[0].managed_transcript_id != ab[1].managed_transcript_id else 1,
            ab[0].embedding_id,
            ab[1].embedding_id,
        )
    )
    if len(same_candidates) > max_same_pairs:
        # Keep preference order for head, then sample remainder cap.
        same_candidates = same_candidates[:max_same_pairs]
    for a, b in same_candidates:
        pairs.append(
            PairScore(
                kind="same",
                profile_a=a.profile_id,
                profile_b=b.profile_id,
                transcript_a=a.managed_transcript_id,
                transcript_b=b.managed_transcript_id,
                embedding_a=a.embedding_id,
                embedding_b=b.embedding_id,
                score=cosine_similarity(a.vector, b.vector),
            )
        )

    # Different-speaker pairs
    profile_ids = sorted(by_profile.keys())
    diff_candidates: list[tuple[EligibleEmbeddingRef, EligibleEmbeddingRef]] = []
    for i, pa in enumerate(profile_ids):
        for pb in profile_ids[i + 1 :]:
            for a in by_profile[pa]:
                for b in by_profile[pb]:
                    diff_candidates.append((a, b))
    if len(diff_candidates) > max_different_pairs:
        idx = rng.choice(len(diff_candidates), size=max_different_pairs, replace=False)
        diff_candidates = [diff_candidates[int(i)] for i in sorted(idx)]
    for a, b in diff_candidates:
        pairs.append(
            PairScore(
                kind="different",
                profile_a=a.profile_id,
                profile_b=b.profile_id,
                transcript_a=a.managed_transcript_id,
                transcript_b=b.managed_transcript_id,
                embedding_a=a.embedding_id,
                embedding_b=b.embedding_id,
                score=cosine_similarity(a.vector, b.vector),
            )
        )
    return pairs


def _rate(numer: int, denom: int) -> float | None:
    if denom <= 0:
        return None
    return numer / denom


def _band_counts(scores: list[float], policy: ThresholdPolicyV1) -> dict[str, int]:
    counts = {"strong": 0, "possible": 0, "weak": 0, "below_candidate": 0}
    for score in scores:
        if score < policy.tau_candidate:
            counts["below_candidate"] += 1
        else:
            counts[confidence_category(score, policy=policy)] += 1
    return counts


def evaluate_pairs(
    pairs: list[PairScore],
    *,
    policy: ThresholdPolicyV1 | None = None,
    profiles_with_eligible_embeddings: int = 0,
    eligible_embedding_count: int = 0,
) -> EvalReport:
    p = policy or PROVISIONAL_THRESHOLDS
    same = [x.score for x in pairs if x.kind == "same"]
    different = [x.score for x in pairs if x.kind == "different"]

    # FAR: different pairs accepted as match at threshold
    # FRR: same pairs rejected below threshold
    far_cand = _rate(sum(1 for s in different if s >= p.tau_candidate), len(different))
    frr_cand = _rate(sum(1 for s in same if s < p.tau_candidate), len(same))
    far_no = _rate(sum(1 for s in different if s >= p.tau_no_match), len(different))
    frr_no = _rate(sum(1 for s in same if s < p.tau_no_match), len(same))

    return EvalReport(
        threshold_policy_id=p.policy_id,
        profiles_with_eligible_embeddings=profiles_with_eligible_embeddings,
        eligible_embedding_count=eligible_embedding_count,
        same_pair_count=len(same),
        different_pair_count=len(different),
        same_scores=same,
        different_scores=different,
        far_at_tau_candidate=far_cand,
        frr_at_tau_candidate=frr_cand,
        far_at_tau_no_match=far_no,
        frr_at_tau_no_match=frr_no,
        same_band_counts=_band_counts(same, p),
        different_band_counts=_band_counts(different, p),
        policy={
            "tau_no_match": p.tau_no_match,
            "tau_candidate": p.tau_candidate,
            "margin": p.margin,
            "strong_min": p.strong_min,
            "possible_min": p.possible_min,
        },
        note=(
            "Thresholds remain provisional until a labeled speaker/recording-held "
            "library run freezes a new threshold_policy_id."
        ),
        recommended_action=(
            "Keep voice_threshold.v1; bump to v2 only after reviewing FAR/FRR on "
            "held-out labeled pairs and updating voice/thresholds.py deliberately."
        ),
    )


def evaluate_speaker_profiles_root(
    root: Path,
    *,
    max_same_pairs: int = 5000,
    max_different_pairs: int = 5000,
    seed: int = 0,
    policy: ThresholdPolicyV1 | None = None,
) -> EvalReport:
    refs = load_eligible_embedding_refs(root)
    pairs = build_held_out_pairs(
        refs,
        max_same_pairs=max_same_pairs,
        max_different_pairs=max_different_pairs,
        seed=seed,
    )
    profiles = {r.profile_id for r in refs}
    return evaluate_pairs(
        pairs,
        policy=policy,
        profiles_with_eligible_embeddings=len(profiles),
        eligible_embedding_count=len(refs),
    )


def write_eval_report(report: EvalReport, out: Path) -> None:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Omit raw score lists from default artifact to keep size bounded; include counts.
    payload = report.to_json_dict()
    payload["same_score_summary"] = _score_summary(report.same_scores)
    payload["different_score_summary"] = _score_summary(report.different_scores)
    del payload["same_scores"]
    del payload["different_scores"]
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _score_summary(scores: list[float]) -> dict[str, float | int | None]:
    if not scores:
        return {"count": 0, "min": None, "max": None, "mean": None, "p50": None}
    arr = np.asarray(scores, dtype=np.float64)
    return {
        "count": int(arr.size),
        "min": float(arr.min()),
        "max": float(arr.max()),
        "mean": float(arr.mean()),
        "p50": float(np.percentile(arr, 50)),
    }
