"""
Group aggregation for contextual_emotion and fine_grained_emotion.

Pooling requires usable_output + complete + segments_scored > 0 and matching
compatibility_fingerprint across members. Incompatible fingerprints are never
blended; each fingerprint cohort is pooled separately and reported.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from transcriptx.core.analysis.aggregation.rows import session_row_from_result
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _extract_module_payload(
    module_results: Dict[str, Any], module_id: str
) -> Dict[str, Any]:
    result = module_results.get(module_id, {})
    if not isinstance(result, dict):
        return {}
    payload = result.get("payload") or result.get("results") or result
    return payload if isinstance(payload, dict) else {}


def _is_poolable(payload: Dict[str, Any]) -> bool:
    return (
        str(payload.get("run_status") or "") == "complete"
        and bool(payload.get("usable_output"))
        and int(payload.get("segments_scored") or 0) > 0
        and bool(payload.get("compatibility_fingerprint"))
    )


def _aggregate_classifier_group(
    *,
    module_id: str,
    per_transcript_results: List[PerTranscriptResult],
    transcript_set: TranscriptSet,
    rates_key: str,
) -> Dict[str, Any] | None:
    cohorts: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    skipped: List[Dict[str, Any]] = []

    for result in per_transcript_results:
        if module_id not in result.module_results:
            continue
        payload = _extract_module_payload(result.module_results, module_id)
        if not payload:
            continue
        if not _is_poolable(payload):
            skipped.append(
                {
                    "transcript_path": result.transcript_path,
                    "reason": "not_poolable",
                    "run_status": payload.get("run_status"),
                    "usable_output": payload.get("usable_output"),
                    "segments_scored": payload.get("segments_scored"),
                }
            )
            continue
        fingerprint = str(payload["compatibility_fingerprint"])
        rates = payload.get(rates_key) or payload.get("primary_rates") or {}
        if not isinstance(rates, dict):
            rates = {}
        cohorts[fingerprint].append(
            session_row_from_result(
                result,
                transcript_set,
                run_id=result.run_id,
                primary_rates=rates,
                release_channel=payload.get("release_channel"),
                profile_id=payload.get("profile_id"),
                compatibility_fingerprint=fingerprint,
            )
        )

    if not cohorts:
        return None

    pooled_by_fingerprint: Dict[str, Any] = {}
    for fingerprint, rows in cohorts.items():
        rows.sort(key=lambda row: row["order_index"])
        keys: set[str] = set()
        for row in rows:
            rates = row.get("primary_rates")
            if isinstance(rates, dict):
                keys.update(rates.keys())
        averaged: Dict[str, float] = {}
        for key in keys:
            vals = [
                float(row["primary_rates"][key])
                for row in rows
                if isinstance(row.get("primary_rates"), dict)
                and key in row["primary_rates"]
                and isinstance(row["primary_rates"][key], (int, float))
            ]
            if vals:
                averaged[key] = sum(vals) / len(vals)
        pooled_by_fingerprint[fingerprint] = {
            "schema_version": 1,
            "compatibility_fingerprint": fingerprint,
            "member_count": len(rows),
            "primary_rates": averaged,
            "session_rows": rows,
        }

    return {
        "module_id": module_id,
        "pooled_by_fingerprint": pooled_by_fingerprint,
        "skipped": skipped,
        # Convenience: if exactly one compatible cohort, expose it at top level.
        "session_rows": (
            next(iter(pooled_by_fingerprint.values()))["session_rows"]
            if len(pooled_by_fingerprint) == 1
            else []
        ),
        "primary_rates_pooled": (
            next(iter(pooled_by_fingerprint.values()))["primary_rates"]
            if len(pooled_by_fingerprint) == 1
            else {}
        ),
    }


def aggregate_contextual_emotion_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    del canonical_speaker_map  # rates are transcript-level in v1
    return _aggregate_classifier_group(
        module_id="contextual_emotion",
        per_transcript_results=per_transcript_results,
        transcript_set=transcript_set,
        rates_key="primary_rates",
    )


def aggregate_fine_grained_emotion_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    del canonical_speaker_map
    return _aggregate_classifier_group(
        module_id="fine_grained_emotion",
        per_transcript_results=per_transcript_results,
        transcript_set=transcript_set,
        rates_key="primary_rates",
    )
