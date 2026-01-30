"""
Group aggregation for interactions module.
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


def _extract_interactions_payload(module_results: Dict[str, Any]) -> Dict[str, Any]:
    interactions_result = module_results.get("interactions", {})
    if not isinstance(interactions_result, dict):
        return {}
    payload = interactions_result.get("payload") or interactions_result.get("results") or {}
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


def _merge_counts(
    aggregate: Dict[int, Dict[str, Any]],
    display_to_canonical: Dict[str, int],
    canonical_speaker_map: CanonicalSpeakerMap,
    counts: Dict[str, int],
    field: str,
) -> None:
    for speaker, value in counts.items():
        canonical_id = display_to_canonical.get(
            speaker, _fallback_canonical_id(speaker)
        )
        entry = aggregate.setdefault(
            canonical_id,
            {
                "canonical_id": canonical_id,
                "display_name": canonical_speaker_map.canonical_to_display.get(
                    canonical_id, speaker
                ),
                "interruptions_initiated": 0,
                "interruptions_received": 0,
                "responses_initiated": 0,
                "responses_received": 0,
                "dominance_score_total": 0.0,
                "dominance_score_count": 0,
            },
        )
        entry[field] += value


def aggregate_interactions_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """
    Aggregate per-transcript interactions results into group-level metrics.

    Returns None when interactions results are missing for all transcripts.
    """
    session_table: List[Dict[str, Any]] = []
    speaker_aggregates: Dict[int, Dict[str, Any]] = {}

    for result in per_transcript_results:
        if "interactions" not in result.module_results:
            continue

        payload = _extract_interactions_payload(result.module_results)
        if not payload:
            continue

        display_to_canonical = _build_display_to_canonical(
            result.transcript_path, canonical_speaker_map
        )

        _merge_counts(
            speaker_aggregates,
            display_to_canonical,
            canonical_speaker_map,
            payload.get("interruption_initiated", {}),
            "interruptions_initiated",
        )
        _merge_counts(
            speaker_aggregates,
            display_to_canonical,
            canonical_speaker_map,
            payload.get("interruption_received", {}),
            "interruptions_received",
        )
        _merge_counts(
            speaker_aggregates,
            display_to_canonical,
            canonical_speaker_map,
            payload.get("responses_initiated", {}),
            "responses_initiated",
        )
        _merge_counts(
            speaker_aggregates,
            display_to_canonical,
            canonical_speaker_map,
            payload.get("responses_received", {}),
            "responses_received",
        )

        dominance_scores = payload.get("dominance_scores", {})
        for speaker, value in dominance_scores.items():
            canonical_id = display_to_canonical.get(
                speaker, _fallback_canonical_id(speaker)
            )
            entry = speaker_aggregates.setdefault(
                canonical_id,
                {
                    "canonical_id": canonical_id,
                    "display_name": canonical_speaker_map.canonical_to_display.get(
                        canonical_id, speaker
                    ),
                    "interruptions_initiated": 0,
                    "interruptions_received": 0,
                    "responses_initiated": 0,
                    "responses_received": 0,
                    "dominance_score_total": 0.0,
                    "dominance_score_count": 0,
                },
            )
            entry["dominance_score_total"] += value
            entry["dominance_score_count"] += 1

        session_table.append(
            {
                "order_index": result.order_index,
                "transcript_path": result.transcript_path,
                "transcript_key": result.transcript_key,
                "run_id": result.run_id,
                "total_interactions": payload.get("total_interactions_count", 0),
                "unique_speakers": payload.get("unique_speakers", 0),
            }
        )

    if not session_table:
        return None

    speaker_rows: List[Dict[str, Any]] = []
    for aggregate in speaker_aggregates.values():
        count = aggregate["dominance_score_count"] or 1
        speaker_rows.append(
            {
                "canonical_id": aggregate["canonical_id"],
                "display_name": aggregate["display_name"],
                "interruptions_initiated": aggregate["interruptions_initiated"],
                "interruptions_received": aggregate["interruptions_received"],
                "responses_initiated": aggregate["responses_initiated"],
                "responses_received": aggregate["responses_received"],
                "dominance_score": aggregate["dominance_score_total"] / count,
            }
        )

    session_table.sort(key=lambda row: row["order_index"])

    return {
        "transcript_set": transcript_set.to_dict(),
        "session_table": session_table,
        "speaker_aggregates": speaker_rows,
    }
