"""Group aggregation for topic_shift — provenance-cohort session comparison."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.aggregation.rows import _session_row_base
from transcriptx.core.analysis.topic_shift.semantics import (
    DEFAULT_MIN_DURATION_FOR_RATE_SECONDS,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult

# Statuses that are valid zero-shift sessions (include in charts with 0)
_ZERO_SHIFT_OK = frozenset({"success", "no_shift_detected"})
# Statuses excluded from numeric comparison (nullable / visible exclude)
_EXCLUDED = frozenset(
    {"insufficient_content", "unsupported_language", "backend_unavailable", "invalid_input"}
)


def _extract_payload(module_results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw = module_results.get("topic_shift")
    if not isinstance(raw, dict):
        return None
    if "stats_envelope" in raw or "stats" in raw:
        return raw
    nested = raw.get("results")
    if isinstance(nested, dict) and (
        "stats_envelope" in nested or "stats" in nested
    ):
        return nested
    return raw


def aggregate_topic_shift(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: Any,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """
    Compare member topic_shift outputs by provenance cohort.

    Never blends MiniLM and TF-IDF (or differing semantics) on one unqualified pool.
    ``no_shift_detected`` is a valid zero-shift session; other abstentions are nullable.
    """
    del canonical_speaker_map
    session_rows: List[Dict[str, Any]] = []
    cohorts: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for result in per_transcript_results:
        payload = _extract_payload(result.module_results)
        if not payload:
            continue
        stats = payload.get("stats_envelope") or payload.get("stats") or {}
        if not isinstance(stats, dict):
            continue
        status = str(stats.get("analytical_status") or "")
        key = str(
            stats.get("provenance_compatibility_key")
            or f"{stats.get('backend')}|{stats.get('model_name')}|{stats.get('semantics_version')}"
        )
        row = _session_row_base(result, transcript_set)
        n_shifts = int(stats.get("n_shifts") or 0)
        valid_dur = stats.get("valid_duration_seconds")
        shifts_per_hour = stats.get("shifts_per_hour")
        min_dur = float(DEFAULT_MIN_DURATION_FOR_RATE_SECONDS)
        if status in _EXCLUDED:
            n_shifts_out: Optional[int] = None
            rate_out: Optional[float] = None
            median_out = None
            longest_out = None
            included = False
        elif status in _ZERO_SHIFT_OK:
            n_shifts_out = n_shifts
            if (
                isinstance(valid_dur, (int, float))
                and float(valid_dur) >= min_dur
                and float(valid_dur) > 0
            ):
                rate_out = (
                    float(shifts_per_hour)
                    if isinstance(shifts_per_hour, (int, float))
                    else (n_shifts / float(valid_dur)) * 3600.0
                )
            else:
                rate_out = None
            median_out = stats.get("median_span_duration")
            longest_out = stats.get("longest_span_duration")
            included = True
        else:
            n_shifts_out = None
            rate_out = None
            median_out = None
            longest_out = None
            included = False

        row.update(
            {
                "analytical_status": status,
                "backend": stats.get("backend"),
                "model_name": stats.get("model_name"),
                "semantics_version": stats.get("semantics_version"),
                "provenance_compatibility_key": key,
                "n_shifts": n_shifts_out,
                "shifts_per_hour": rate_out,
                "median_span_duration": median_out,
                "longest_span_duration": longest_out,
                "valid_duration_seconds": valid_dur,
                "included_in_comparison": included,
            }
        )
        session_rows.append(row)
        if included:
            cohorts[key].append(row)

    if not session_rows:
        return None

    # Primary cohort = largest included set
    primary_key = ""
    if cohorts:
        primary_key = max(cohorts.keys(), key=lambda k: (len(cohorts[k]), k))

    primary_rows = cohorts.get(primary_key) or []
    incompatible = sum(
        1
        for r in session_rows
        if r.get("included_in_comparison")
        and str(r.get("provenance_compatibility_key") or "") != primary_key
    )
    excluded = sum(1 for r in session_rows if not r.get("included_in_comparison"))

    return {
        "session_rows": session_rows,
        "topic_shift_pooled": {
            "comparable_key": primary_key,
            "member_count": len(primary_rows),
            "incompatible_member_count": incompatible,
            "excluded_abstention_count": excluded,
            "backend": primary_rows[0].get("backend") if primary_rows else None,
            "semantics_version": (
                primary_rows[0].get("semantics_version") if primary_rows else None
            ),
        },
    }
