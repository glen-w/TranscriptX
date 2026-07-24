"""Salience scoring, direction conversion, and rank weights for keyphrases."""

from __future__ import annotations

import math
from typing import Sequence

from transcriptx.core.analysis.keyphrases.contract import (
    RankedPhrase,
    ScoreDirection,
    round_score,
)

__all__ = [
    "assign_ranks_and_weights",
    "base_salience",
    "higher_is_better_salience",
    "length_ok",
    "min_max_weights",
    "round_score",
    "sort_key_for_weight",
]


def length_ok(token_count: int, *, min_tokens: int, max_tokens: int) -> bool:
    return min_tokens <= int(token_count) <= max_tokens


def base_salience(
    *,
    occurrence_count: int,
    segment_support: int,
    token_count: int,
) -> float:
    """Noun-chunk base score before quality adjustments."""
    _ = token_count  # length enforced by hard reject; factor is 1.0 inside bounds
    return float(occurrence_count) * math.log1p(float(segment_support))


def higher_is_better_salience(
    raw_score: float, direction: ScoreDirection
) -> float:
    if direction == "higher_is_better":
        return float(raw_score)
    return -float(raw_score)


def min_max_weights(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi <= lo:
        return [1.0 for _ in values]
    span = hi - lo
    return [(float(v) - lo) / span for v in values]


def sort_key_for_weight(
    *,
    rank_weight: float,
    occurrence_count: int,
    token_count: int,
    canonical_key: str,
) -> tuple:
    return (-rank_weight, -occurrence_count, -token_count, canonical_key)


def assign_ranks_and_weights(
    phrases: list[RankedPhrase],
) -> list[RankedPhrase]:
    """Normalise rank_weight within list and assign dense ranks with stable ties."""
    if not phrases:
        return []
    saliences = [
        higher_is_better_salience(p.raw_score, p.score_direction) for p in phrases
    ]
    weights = min_max_weights(saliences)
    decorated: list[RankedPhrase] = []
    for phrase, weight in zip(phrases, weights):
        decorated.append(
            phrase.model_copy(
                update={
                    "raw_score": round_score(phrase.raw_score),
                    "rank_weight": round_score(max(0.0, float(weight))),
                }
            )
        )
    decorated.sort(
        key=lambda p: sort_key_for_weight(
            rank_weight=p.rank_weight,
            occurrence_count=p.occurrence_count,
            token_count=p.token_count,
            canonical_key=p.canonical_key,
        )
    )
    out: list[RankedPhrase] = []
    for idx, phrase in enumerate(decorated, start=1):
        out.append(phrase.model_copy(update={"rank": idx}))
    return out
