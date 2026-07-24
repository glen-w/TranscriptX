"""Provisional threshold policy (freeze after Stage 4 evaluation)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from transcriptx.core.speaker_profiles.voice.versioning import THRESHOLD_POLICY_ID

ConfidenceCategory = Literal["strong", "possible", "weak"]


@dataclass(frozen=True)
class ThresholdPolicyV1:
    """Score bands are categories — not calibrated probabilities."""

    policy_id: str = THRESHOLD_POLICY_ID
    tau_no_match: float = 0.65
    tau_candidate: float = 0.70
    margin: float = 0.05
    top_k_refs_per_query: int = 3
    max_candidates: int = 3
    strong_min: float = 0.85
    possible_min: float = 0.75
    # weak: >= tau_candidate and < possible_min


PROVISIONAL_THRESHOLDS = ThresholdPolicyV1()


def confidence_category(
    score: float, *, policy: ThresholdPolicyV1 | None = None
) -> ConfidenceCategory:
    p = policy or PROVISIONAL_THRESHOLDS
    if score >= p.strong_min:
        return "strong"
    if score >= p.possible_min:
        return "possible"
    return "weak"
