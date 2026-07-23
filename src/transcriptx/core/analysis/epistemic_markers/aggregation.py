"""Group aggregation for epistemic_markers."""

from __future__ import annotations

from typing import Any, Dict, List

from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def aggregate_epistemic_markers(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    from transcriptx.core.analysis.aggregation.registry import (
        _build_rows_from_stats,
        _extract_payload,
        _warning_payload_shape,
    )

    session_rows: List[Dict[str, Any]] = []
    speaker_rows: List[Dict[str, Any]] = []
    by_category: Dict[str, int] = {}
    total_hits = 0
    rate_values: List[float] = []

    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "epistemic_markers")
        if not payload:
            continue
        speaker_stats = payload.get("speaker_stats") or {}
        global_stats = payload.get("global_stats") or {}
        if not isinstance(global_stats, dict) or not isinstance(speaker_stats, dict):
            return _warning_payload_shape(
                "epistemic_markers", ["global_stats", "speaker_stats"]
            )
        counts = global_stats.get("category_counts") or {}
        if isinstance(counts, dict):
            for key, value in counts.items():
                if isinstance(value, (int, float)):
                    by_category[str(key)] = by_category.get(str(key), 0) + int(value)
        th = global_stats.get("total_marker_hits")
        if isinstance(th, (int, float)):
            total_hits += int(th)
        rate = global_stats.get("hits_per_100_tokens")
        if isinstance(rate, (int, float)):
            rate_values.append(float(rate))
        # Flatten category counts into top-level for row builders / charts
        flat_global = {
            "total_marker_hits": global_stats.get("total_marker_hits"),
            "token_count": global_stats.get("token_count"),
            "hits_per_100_tokens": global_stats.get("hits_per_100_tokens"),
            "hedge_share": global_stats.get("hedge_share"),
            "booster_share": global_stats.get("booster_share"),
        }
        flat_speakers: Dict[str, Dict[str, Any]] = {}
        for speaker, stats in speaker_stats.items():
            if not isinstance(stats, dict):
                continue
            flat_speakers[speaker] = {
                "total_marker_hits": stats.get("total_marker_hits"),
                "token_count": stats.get("token_count"),
                "hits_per_100_tokens": stats.get("hits_per_100_tokens"),
                "hedge_share": stats.get("hedge_share"),
                "booster_share": stats.get("booster_share"),
            }
        rows = _build_rows_from_stats(
            result, transcript_set, canonical_speaker_map, flat_global, flat_speakers
        )
        session_rows.extend(rows["session_rows"])
        speaker_rows.extend(rows["speaker_rows"])

    if not session_rows:
        return None

    mean_rate = sum(rate_values) / len(rate_values) if rate_values else None
    pooled = {
        "schema_version": 1,
        "total_marker_hits": total_hits,
        "by_category": dict(sorted(by_category.items(), key=lambda kv: -kv[1])),
        "mean_hits_per_100_tokens": mean_rate,
        "rate_pooling_note": (
            "mean_hits_per_100_tokens is a descriptive session mean, not an exact "
            "token-weighted pool."
        ),
    }
    return {
        "session_rows": session_rows,
        "speaker_rows": speaker_rows,
        "epistemic_markers_pooled": pooled,
    }
