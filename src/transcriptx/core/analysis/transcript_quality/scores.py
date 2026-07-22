"""ASR word-score acceptance and normalisation diagnostics.

Policy: ``accept_unit_interval_omit_otherwise``.
Finite numeric scores in ``[0, 1]`` are accepted; others are omitted (never clamped).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

NORMALISATION_POLICY = "accept_unit_interval_omit_otherwise"
SOURCE_SCORE_FIELD = "score"

DISCLAIMER = (
    "ASR confidence is model-produced uncertainty evidence, not an estimated "
    "word error rate and not proof that a word is incorrect."
)


@dataclass(frozen=True)
class ScoreVerdict:
    """Result of inspecting one word's score field."""

    accepted: Optional[float]
    raw_present: bool
    invalid: bool
    out_of_range: bool


def classify_score(raw: Any) -> ScoreVerdict:
    """Classify a raw score value under the unit-interval omit policy."""
    if raw is None:
        return ScoreVerdict(
            accepted=None, raw_present=False, invalid=False, out_of_range=False
        )
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return ScoreVerdict(
            accepted=None, raw_present=True, invalid=True, out_of_range=False
        )
    if value != value or value in (float("inf"), float("-inf")):  # NaN / ±inf
        return ScoreVerdict(
            accepted=None, raw_present=True, invalid=True, out_of_range=False
        )
    if value < 0.0 or value > 1.0:
        return ScoreVerdict(
            accepted=None, raw_present=True, invalid=False, out_of_range=True
        )
    return ScoreVerdict(
        accepted=value, raw_present=True, invalid=False, out_of_range=False
    )


def normalize_word_dict(word: Dict[str, Any]) -> Tuple[Dict[str, Any], ScoreVerdict]:
    """
    Return a shallow-copied word with score accepted or omitted.

    Never clamps out-of-range values; invalid/out-of-range scores are dropped
    from the copy while other word fields are preserved.
    """
    out = dict(word)
    verdict = classify_score(word.get(SOURCE_SCORE_FIELD))
    if verdict.accepted is None:
        out.pop(SOURCE_SCORE_FIELD, None)
    else:
        out[SOURCE_SCORE_FIELD] = verdict.accepted
    return out, verdict


def normalize_words_list(
    words: Optional[List[Dict[str, Any]]],
) -> Tuple[Optional[List[Dict[str, Any]]], Dict[str, int]]:
    """Normalise a segment words list; return diagnostics counters."""
    diagnostics = {
        "raw_score_present_count": 0,
        "accepted_score_count": 0,
        "invalid_score_count": 0,
        "out_of_range_score_count": 0,
    }
    if words is None:
        return None, diagnostics
    if not isinstance(words, list):
        return None, diagnostics

    normalised: List[Dict[str, Any]] = []
    for item in words:
        if not isinstance(item, dict):
            continue
        cleaned, verdict = normalize_word_dict(item)
        if verdict.raw_present:
            diagnostics["raw_score_present_count"] += 1
        if verdict.accepted is not None:
            diagnostics["accepted_score_count"] += 1
        if verdict.invalid:
            diagnostics["invalid_score_count"] += 1
        if verdict.out_of_range:
            diagnostics["out_of_range_score_count"] += 1
        normalised.append(cleaned)
    return normalised, diagnostics


def merge_score_diagnostics(*parts: Dict[str, int]) -> Dict[str, int]:
    """Sum diagnostic counters across segments."""
    keys = (
        "raw_score_present_count",
        "accepted_score_count",
        "invalid_score_count",
        "out_of_range_score_count",
    )
    out = {k: 0 for k in keys}
    for part in parts:
        for k in keys:
            out[k] += int(part.get(k, 0) or 0)
    return out


def empty_score_normalisation() -> Dict[str, Any]:
    return {
        "raw_score_present_count": 0,
        "accepted_score_count": 0,
        "invalid_score_count": 0,
        "out_of_range_score_count": 0,
        "policy": NORMALISATION_POLICY,
    }
