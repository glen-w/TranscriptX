"""Pure ASR confidence analysis (no I/O)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from transcriptx.core.analysis.transcript_quality.provenance import build_provenance
from transcriptx.core.analysis.transcript_quality.scores import DISCLAIMER
from transcriptx.core.analysis.transcript_quality.spans import (
    SpanBuildConfig,
    build_spans_and_clusters,
)
from transcriptx.core.analysis.transcript_quality.words import extract_word_records

SCHEMA_VERSION = 1
SEMANTIC_VERSION = "transcript_quality.asr_confidence.v1"


def _percentile(sorted_vals: Sequence[float], p: float) -> Optional[float]:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    rank = (len(sorted_vals) - 1) * p
    low = int(rank)
    high = min(low + 1, len(sorted_vals) - 1)
    weight = rank - low
    return float(sorted_vals[low] * (1.0 - weight) + sorted_vals[high] * weight)


def _status(*, scored: int, eligible: int) -> str:
    if scored == 0:
        return "absent"
    if scored < eligible:
        return "partial"
    return "present"


def compute_asr_confidence(
    segments: List[Dict[str, Any]],
    *,
    cfg: SpanBuildConfig,
    provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute ASR confidence payload from transcript segments."""
    words, normalisation = extract_word_records(segments)
    eligible = [w for w in words if w.eligible]
    scored_words = [w for w in eligible if w.score is not None]
    scores = sorted(float(w.score) for w in scored_words if w.score is not None)

    eligible_word_count = len(eligible)
    scored_word_count = len(scored_words)
    missing_score_count = sum(1 for w in eligible if w.missing_score)
    invalid_score_count = sum(1 for w in eligible if w.invalid_score)
    out_of_range_score_count = sum(1 for w in eligible if w.out_of_range_score)
    excluded_unusable_count = sum(1 for w in words if w.unusable)

    status = _status(scored=scored_word_count, eligible=eligible_word_count)
    coverage_ratio = (
        (scored_word_count / eligible_word_count) if eligible_word_count > 0 else None
    )

    low_score_words = [
        w
        for w in scored_words
        if w.score is not None and w.score < cfg.low_score_threshold
    ]
    low_score_word_count = len(low_score_words)
    low_score_ratio = (
        (low_score_word_count / scored_word_count) if scored_word_count > 0 else None
    )

    span_payload = (
        build_spans_and_clusters(words, cfg)
        if scored_word_count > 0
        else {
            "spans_total_count": 0,
            "spans_emitted_count": 0,
            "clusters_total_count": 0,
            "clusters_emitted_count": 0,
            "spans": [],
            "clusters": [],
        }
    )

    mean_score = (sum(scores) / len(scores)) if scores else None

    asr_confidence: Dict[str, Any] = {
        "status": status,
        "eligible_word_count": eligible_word_count,
        "scored_word_count": scored_word_count,
        "coverage_ratio": coverage_ratio,
        "missing_score_count": missing_score_count,
        "invalid_score_count": invalid_score_count,
        "out_of_range_score_count": out_of_range_score_count,
        "excluded_unusable_count": excluded_unusable_count,
        "score_normalisation": normalisation,
        "mean_score": mean_score,
        "p10": _percentile(scores, 0.10),
        "p50": _percentile(scores, 0.50),
        "p90": _percentile(scores, 0.90),
        "low_score_threshold": cfg.low_score_threshold,
        "low_score_word_count": low_score_word_count,
        "low_score_ratio": low_score_ratio,
        **span_payload,
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "semantic_version": SEMANTIC_VERSION,
        "disclaimer": DISCLAIMER,
        "provenance": provenance or build_provenance(),
        "asr_confidence": asr_confidence,
    }


def score_histogram_bins(
    scores: Sequence[float],
    *,
    bin_count: int = 10,
) -> Dict[str, Any]:
    """Build histogram categories/values over accepted scores in [0, 1]."""
    values = [float(s) for s in scores]
    if bin_count < 1:
        bin_count = 1
    edges = [i / bin_count for i in range(bin_count + 1)]
    counts = [0 for _ in range(bin_count)]
    for score in values:
        if score >= 1.0:
            counts[-1] += 1
            continue
        idx = min(int(score * bin_count), bin_count - 1)
        counts[idx] += 1
    categories = [f"{edges[i]:.1f}-{edges[i + 1]:.1f}" for i in range(bin_count)]
    return {"categories": categories, "counts": counts, "scores": values}
