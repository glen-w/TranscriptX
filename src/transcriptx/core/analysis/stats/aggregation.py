"""
Group aggregation for stats module.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from transcriptx.core.analysis.aggregation.rows import (
    _build_display_to_canonical,
    _fallback_canonical_id,
    session_row_from_result,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _extract_stats_payload(module_results: Dict[str, Any]) -> Dict[str, Any]:
    stats_result = module_results.get("stats", {})
    if not isinstance(stats_result, dict):
        return {}
    payload = stats_result.get("payload") or stats_result.get("results") or {}
    return payload if isinstance(payload, dict) else {}


def aggregate_stats_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """
    Aggregate per-transcript stats results into group-level metrics.
    """
    session_rows: List[Dict[str, Any]] = []
    speaker_aggregates: Dict[int, Dict[str, Any]] = {}

    for result in per_transcript_results:
        payload = _extract_stats_payload(result.module_results)
        speaker_stats: List[Tuple[float, str, int, int, float, float]] = payload.get(
            "speaker_stats", []
        )
        sentiment_summary: Dict[str, Dict[str, float]] = payload.get(
            "sentiment_summary", {}
        )

        total_words = 0
        total_segments = 0
        total_duration = 0.0

        display_to_canonical = _build_display_to_canonical(
            result.transcript_path, canonical_speaker_map
        )

        for duration, name, word_count, segment_count, tic_rate, _ in speaker_stats:
            total_words += word_count
            total_segments += segment_count
            total_duration += duration

            canonical_id = display_to_canonical.get(
                name, _fallback_canonical_id(name)
            )
            aggregate = speaker_aggregates.setdefault(
                canonical_id,
                {
                    "canonical_speaker_id": canonical_id,
                    "display_name": canonical_speaker_map.canonical_to_display.get(
                        canonical_id, name
                    ),
                    "total_duration": 0.0,
                    "total_word_count": 0,
                    "total_segment_count": 0,
                    "total_tic_count": 0.0,
                    "sentiment_weighted": {"compound": 0.0, "pos": 0.0, "neu": 0.0, "neg": 0.0},
                    "sentiment_weight": 0.0,
                },
            )

            aggregate["total_duration"] += duration
            aggregate["total_word_count"] += word_count
            aggregate["total_segment_count"] += segment_count
            aggregate["total_tic_count"] += tic_rate * word_count

            sentiment = sentiment_summary.get(name, {})
            weight = segment_count if segment_count else 1
            aggregate["sentiment_weighted"]["compound"] += sentiment.get(
                "compound", 0.0
            ) * weight
            aggregate["sentiment_weighted"]["pos"] += sentiment.get("pos", 0.0) * weight
            aggregate["sentiment_weighted"]["neu"] += sentiment.get("neu", 0.0) * weight
            aggregate["sentiment_weighted"]["neg"] += sentiment.get("neg", 0.0) * weight
            aggregate["sentiment_weight"] += weight

        session_rows.append(
            session_row_from_result(
                result,
                transcript_set,
                run_id=result.run_id,
                speaker_count=len(speaker_stats),
                total_words=total_words,
                total_segments=total_segments,
                total_duration=total_duration,
            )
        )

    speaker_rows: List[Dict[str, Any]] = []
    for aggregate in speaker_aggregates.values():
        weight = aggregate["sentiment_weight"] or 1
        sentiment = {
            "compound": aggregate["sentiment_weighted"]["compound"] / weight,
            "pos": aggregate["sentiment_weighted"]["pos"] / weight,
            "neu": aggregate["sentiment_weighted"]["neu"] / weight,
            "neg": aggregate["sentiment_weighted"]["neg"] / weight,
        }
        speaker_rows.append(
            {
                "canonical_speaker_id": aggregate["canonical_speaker_id"],
                "display_name": aggregate["display_name"],
                "total_duration": aggregate["total_duration"],
                "total_word_count": aggregate["total_word_count"],
                "total_segment_count": aggregate["total_segment_count"],
                "avg_segment_len": (
                    aggregate["total_word_count"] / aggregate["total_segment_count"]
                    if aggregate["total_segment_count"]
                    else 0.0
                ),
                "tic_rate": (
                    aggregate["total_tic_count"] / aggregate["total_word_count"]
                    if aggregate["total_word_count"]
                    else 0.0
                ),
                "sentiment": sentiment,
            }
        )

    session_rows.sort(key=lambda row: row["order_index"])

    if not session_rows:
        return None

    return {
        "session_rows": session_rows,
        "speaker_rows": speaker_rows,
    }
