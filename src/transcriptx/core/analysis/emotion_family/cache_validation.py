"""Validate inference-cache score rows before reuse."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


def _finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def validate_classifier_cache_row(
    row: Mapping[str, Any] | None,
    *,
    expected_labels: Sequence[str] | None = None,
    activation: str | None = None,
    expected_scored_text_hash: str | None = None,
) -> bool:
    """
    Return True when a cached classifier score row is structurally valid.

    Checks presence of scores, finite probabilities, optional label-set
    equality, truncation metadata, scored_text_hash, and (when
    activation=softmax) that probabilities approximately sum to 1.
    """
    if not isinstance(row, Mapping):
        return False
    scores = row.get("scores")
    if not isinstance(scores, dict) or not scores:
        return False
    if "truncated" not in row:
        return False
    if not isinstance(row.get("truncated"), bool):
        return False
    omitted = row.get("omitted_token_count_lower_bound", row.get("omitted_token_count"))
    if omitted is not None:
        if not isinstance(omitted, int) or isinstance(omitted, bool) or omitted < 0:
            return False
    truncated = bool(row.get("truncated"))
    if truncated and (omitted is None or int(omitted) < 1):
        return False
    if not truncated and omitted is not None and int(omitted) != 0:
        # Non-truncated rows may omit the field; if present it must be zero.
        return False
    text_hash = str(row.get("scored_text_hash") or "").strip()
    if not text_hash:
        return False
    if expected_scored_text_hash is not None and text_hash != str(
        expected_scored_text_hash
    ):
        return False
    for label, value in scores.items():
        if not isinstance(label, str) or not label:
            return False
        if not _finite_number(value):
            return False
        fval = float(value)
        if fval < 0.0 or fval > 1.0 + 1e-6:
            return False
    if expected_labels is not None:
        expected = {lab.casefold() for lab in expected_labels}
        got = {str(k).casefold() for k in scores}
        if got != expected:
            return False
    if activation == "softmax":
        total = sum(float(v) for v in scores.values())
        if abs(total - 1.0) > 0.05:
            return False
    return True


def validate_lexical_cache_row(
    row: Mapping[str, Any] | None,
    *,
    expected_scored_text_hash: str | None = None,
) -> bool:
    """Return True when a cached lexical score row has required fields."""
    if not isinstance(row, Mapping):
        return False
    state = row.get("evaluation_state")
    if state not in {"scored", "empty", "skipped", "failed"}:
        return False
    text_hash = str(row.get("scored_text_hash") or "").strip()
    if not text_hash:
        return False
    if expected_scored_text_hash is not None and text_hash != str(
        expected_scored_text_hash
    ):
        return False
    for key in (
        "coverage",
        "tokens_considered",
        "matched_occurrences",
        "assignment_counts",
        "emotion_scores",
    ):
        if key not in row:
            return False
    if not _finite_number(row.get("coverage")):
        return False
    coverage = float(row.get("coverage"))
    if coverage < 0.0 or coverage > 1.0 + 1e-6:
        return False
    for count_key in ("tokens_considered", "matched_occurrences"):
        value = row.get(count_key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            return False
    if not isinstance(row.get("assignment_counts"), dict):
        return False
    for _label, count in (row.get("assignment_counts") or {}).items():
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            return False
    if not isinstance(row.get("emotion_scores"), dict):
        return False
    for _label, score in (row.get("emotion_scores") or {}).items():
        if not _finite_number(score):
            return False
    return True
