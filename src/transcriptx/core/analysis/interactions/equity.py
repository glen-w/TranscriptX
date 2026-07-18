"""Turn-taking equity metrics for interactions (deterministic, side-effect-free)."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from transcriptx.core.analysis.interactions.events import InteractionEvent
from transcriptx.core.analysis.interactions.roles import (
    RESPONSE_TYPE,
    resolve_interaction_roles,
)
from transcriptx.core.utils.segment_duration import SpeakerDurationResult

# Stable abstention reason codes
ABSTAIN_FEWER_THAN_TWO_ELIGIBLE = "fewer_than_two_eligible_speakers"
ABSTAIN_ZERO_TOTAL_DURATION = "zero_total_duration"
ABSTAIN_NO_INTERRUPTIONS = "no_interruptions"
ABSTAIN_FEWER_THAN_TWO_VALID_RESPONDERS = "fewer_than_two_valid_responders"
ABSTAIN_ZERO_OVERALL_MEAN_LATENCY = "zero_overall_mean_latency"

EQUITY_SCHEMA_FIELDS = (
    "floor_share",
    "floor_entropy",
    "floor_equity_index",
    "interruption_asymmetry",
    "interruption_asymmetry_index",
    "response_latency",
    "response_latency_fairness_index",
    "abstentions",
)


def nearest_rank_p90(values: Sequence[float]) -> float:
    """Nearest-rank p90: sort ascending; index ceil(0.9 * n) - 1 (0-based)."""
    if not values:
        raise ValueError("nearest_rank_p90 requires a non-empty sample")
    ordered = sorted(values)
    n = len(ordered)
    idx = math.ceil(0.9 * n) - 1
    idx = max(0, min(idx, n - 1))
    return float(ordered[idx])


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return float(ordered[mid])
    return (float(ordered[mid - 1]) + float(ordered[mid])) / 2.0


def _is_valid_gap(value: Any) -> bool:
    if value is None:
        return False
    try:
        gap = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(gap) and gap >= 0.0


def _population_cv(means: Sequence[float]) -> float | None:
    n = len(means)
    if n == 0:
        return None
    mu = sum(means) / n
    if mu == 0.0:
        return None
    var = sum((x - mu) ** 2 for x in means) / n
    sigma = math.sqrt(var)
    return sigma / mu


def _abstention(metric: str, reason: str) -> dict[str, str]:
    return {"metric": metric, "reason": reason}


def empty_equity(*, abstentions: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Canonical equity object with null scalars and empty maps."""
    return {
        "floor_share": {},
        "floor_entropy": None,
        "floor_equity_index": None,
        "interruption_asymmetry": {},
        "interruption_asymmetry_index": None,
        "response_latency": {},
        "response_latency_fairness_index": None,
        "abstentions": list(abstentions or []),
    }


def compute_equity(
    *,
    duration_result: SpeakerDurationResult,
    interruption_initiated: Mapping[str, int],
    interruption_received: Mapping[str, int],
    interactions: Sequence[InteractionEvent | Mapping[str, Any]],
) -> dict[str, Any]:
    """
    Compute the canonical equity object from durations, corrected counts, and events.

    Scalars are always float|null; maps always dict; abstentions are {metric, reason}.
    ``interruption_balance_index`` is not included (presentation-derived only).
    """
    abstentions: list[dict[str, str]] = []
    equity = empty_equity()

    # --- Floor share / entropy / equity index ---
    eligible = list(duration_result.eligible_speakers)
    n = len(eligible)
    total = float(duration_result.total_valid_duration)

    if n < 2:
        abstentions.append(
            _abstention("floor_equity_index", ABSTAIN_FEWER_THAN_TWO_ELIGIBLE)
        )
        abstentions.append(
            _abstention("floor_entropy", ABSTAIN_FEWER_THAN_TWO_ELIGIBLE)
        )
    elif total <= 0.0:
        abstentions.append(
            _abstention("floor_equity_index", ABSTAIN_ZERO_TOTAL_DURATION)
        )
        abstentions.append(_abstention("floor_entropy", ABSTAIN_ZERO_TOTAL_DURATION))
    else:
        floor_share = {
            speaker: float(duration_result.durations.get(speaker, 0.0)) / total
            for speaker in eligible
        }
        equity["floor_share"] = floor_share
        entropy = 0.0
        for p in floor_share.values():
            if p > 0.0:
                entropy -= p * math.log2(p)
        equity["floor_entropy"] = float(entropy)
        equity["floor_equity_index"] = float(entropy / math.log2(n))

    # --- Interruption asymmetry ---
    involved: list[str] = sorted(
        set(interruption_initiated) | set(interruption_received)
    )
    asymmetry_map: dict[str, float] = {}
    for speaker in involved:
        initiated = int(interruption_initiated.get(speaker, 0))
        received = int(interruption_received.get(speaker, 0))
        denom = initiated + received
        if denom <= 0:
            continue
        asymmetry_map[speaker] = (initiated - received) / denom

    total_interruptions = sum(int(v) for v in interruption_initiated.values())
    if total_interruptions <= 0 or not asymmetry_map:
        abstentions.append(
            _abstention("interruption_asymmetry_index", ABSTAIN_NO_INTERRUPTIONS)
        )
        equity["interruption_asymmetry"] = {}
    else:
        equity["interruption_asymmetry"] = asymmetry_map
        mean_abs = sum(abs(v) for v in asymmetry_map.values()) / len(asymmetry_map)
        equity["interruption_asymmetry_index"] = float(mean_abs)

    # --- Response latency (per responder = actor for response events) ---
    gaps_by_responder: dict[str, list[float]] = {}
    for raw in interactions:
        if isinstance(raw, InteractionEvent):
            event = raw
        else:
            try:
                event = InteractionEvent(**dict(raw))
            except TypeError:
                continue
        if event.interaction_type != RESPONSE_TYPE:
            continue
        roles = resolve_interaction_roles(event)
        if roles is None:
            continue
        if not _is_valid_gap(event.gap_before):
            continue
        gaps_by_responder.setdefault(roles.actor, []).append(float(event.gap_before))

    response_latency: dict[str, dict[str, float | int]] = {}
    means: list[float] = []
    for responder in sorted(gaps_by_responder):
        gaps = gaps_by_responder[responder]
        if not gaps:
            continue
        mean_v = sum(gaps) / len(gaps)
        response_latency[responder] = {
            "count": len(gaps),
            "mean": float(mean_v),
            "median": float(_median(gaps)),
            "p90": float(nearest_rank_p90(gaps)),
        }
        means.append(mean_v)

    equity["response_latency"] = response_latency

    if len(means) < 2:
        abstentions.append(
            _abstention(
                "response_latency_fairness_index",
                ABSTAIN_FEWER_THAN_TWO_VALID_RESPONDERS,
            )
        )
    else:
        overall_mean = sum(means) / len(means)
        if overall_mean == 0.0:
            abstentions.append(
                _abstention(
                    "response_latency_fairness_index",
                    ABSTAIN_ZERO_OVERALL_MEAN_LATENCY,
                )
            )
        else:
            cv = _population_cv(means)
            if cv is None:
                abstentions.append(
                    _abstention(
                        "response_latency_fairness_index",
                        ABSTAIN_ZERO_OVERALL_MEAN_LATENCY,
                    )
                )
            else:
                fairness = max(0.0, min(1.0, 1.0 - cv))
                equity["response_latency_fairness_index"] = float(fairness)

    equity["abstentions"] = abstentions
    return equity
