"""
Group aggregation for sentiment module.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _fallback_canonical_id(label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _extract_sentiment_payload(module_results: Dict[str, Any]) -> Dict[str, Any]:
    sentiment_result = module_results.get("sentiment", {})
    if not isinstance(sentiment_result, dict):
        return {}
    payload = sentiment_result.get("payload") or sentiment_result.get("results") or {}
    return payload if isinstance(payload, dict) else {}


def _build_display_to_canonical(
    transcript_path: str, canonical_speaker_map: CanonicalSpeakerMap
) -> Dict[str, int]:
    local_to_canonical = canonical_speaker_map.transcript_to_speakers.get(
        transcript_path, {}
    )
    local_to_display = canonical_speaker_map.transcript_to_display.get(
        transcript_path, {}
    )
    display_to_canonical: Dict[str, int] = {}
    for local_id, canonical_id in local_to_canonical.items():
        display_name = local_to_display.get(local_id, local_id)
        display_to_canonical[display_name] = canonical_id
    return display_to_canonical


def aggregate_sentiment_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """
    Aggregate per-transcript sentiment results into group-level metrics.

    Returns None when sentiment results are missing for all transcripts.
    """
    session_table: List[Dict[str, Any]] = []
    speaker_aggregates: Dict[int, Dict[str, Any]] = {}

    for result in per_transcript_results:
        if "sentiment" not in result.module_results:
            continue

        payload = _extract_sentiment_payload(result.module_results)
        if not payload:
            continue

        speaker_stats = payload.get("speaker_stats", {})
        global_stats = payload.get("global_stats", {})
        display_to_canonical = _build_display_to_canonical(
            result.transcript_path, canonical_speaker_map
        )

        for speaker, stats in speaker_stats.items():
            if not isinstance(stats, dict):
                continue
            canonical_id = display_to_canonical.get(
                speaker, _fallback_canonical_id(speaker)
            )
            aggregate = speaker_aggregates.setdefault(
                canonical_id,
                {
                    "canonical_id": canonical_id,
                    "display_name": canonical_speaker_map.canonical_to_display.get(
                        canonical_id, speaker
                    ),
                    "segment_count": 0,
                    "compound_weighted": 0.0,
                    "pos_weighted": 0.0,
                    "neu_weighted": 0.0,
                    "neg_weighted": 0.0,
                },
            )

            count = stats.get("count", 0) or 1
            aggregate["segment_count"] += count
            aggregate["compound_weighted"] += stats.get("compound_mean", 0.0) * count
            aggregate["pos_weighted"] += stats.get("pos_mean", 0.0) * count
            aggregate["neu_weighted"] += stats.get("neu_mean", 0.0) * count
            aggregate["neg_weighted"] += stats.get("neg_mean", 0.0) * count

        session_table.append(
            {
                "order_index": result.order_index,
                "transcript_path": result.transcript_path,
                "transcript_key": result.transcript_key,
                "run_id": result.run_id,
                "segment_count": global_stats.get("count", 0),
                "compound_mean": global_stats.get("compound_mean", 0.0),
                "pos_mean": global_stats.get("pos_mean", 0.0),
                "neu_mean": global_stats.get("neu_mean", 0.0),
                "neg_mean": global_stats.get("neg_mean", 0.0),
            }
        )

    if not session_table:
        return None

    speaker_rows: List[Dict[str, Any]] = []
    for aggregate in speaker_aggregates.values():
        count = aggregate["segment_count"] or 1
        speaker_rows.append(
            {
                "canonical_id": aggregate["canonical_id"],
                "display_name": aggregate["display_name"],
                "segment_count": aggregate["segment_count"],
                "compound_mean": aggregate["compound_weighted"] / count,
                "pos_mean": aggregate["pos_weighted"] / count,
                "neu_mean": aggregate["neu_weighted"] / count,
                "neg_mean": aggregate["neg_weighted"] / count,
            }
        )

    session_table.sort(key=lambda row: row["order_index"])

    return {
        "transcript_set": transcript_set.to_dict(),
        "session_table": session_table,
        "speaker_aggregates": speaker_rows,
    }
