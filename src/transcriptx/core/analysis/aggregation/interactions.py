"""
Group aggregation for interactions module.
"""

from __future__ import annotations

from typing import Any, Dict, List

from transcriptx.core.analysis.aggregation.rows import (
    _build_display_to_canonical,
    _fallback_canonical_id,
    session_row_from_result,
)
from transcriptx.core.analysis.aggregation.warnings import build_warning
from transcriptx.core.analysis.interactions.roles import INTERACTIONS_SEMANTICS_VERSION
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _extract_interactions_payload(module_results: Dict[str, Any]) -> Dict[str, Any]:
    interactions_result = module_results.get("interactions", {})
    if not isinstance(interactions_result, dict):
        return {}
    payload = (
        interactions_result.get("payload") or interactions_result.get("results") or {}
    )
    return payload if isinstance(payload, dict) else {}


def _payload_semantics_version(payload: Dict[str, Any]) -> int | None:
    raw = payload.get("semantics_version")
    if raw is None:
        equity = payload.get("equity")
        if isinstance(equity, dict) and equity.get("semantics_version") is not None:
            raw = equity.get("semantics_version")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _equity_index(payload: Dict[str, Any], key: str) -> float | None:
    equity = payload.get("equity")
    if not isinstance(equity, dict):
        return None
    value = equity.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
                "canonical_speaker_id": canonical_id,
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

    Directional pooling (role counts, dominance-derived speaker_rows) requires every
    included payload to use ``semantics_version == INTERACTIONS_SEMANTICS_VERSION``.
    Session rows (including nullable equity indices) are always produced per run.
    """
    session_rows: List[Dict[str, Any]] = []
    speaker_aggregates: Dict[int, Dict[str, Any]] = {}
    aggregation_warnings: List[Dict[str, Any]] = []

    versioned_payloads: List[tuple[PerTranscriptResult, Dict[str, Any], int | None]] = []

    for result in per_transcript_results:
        if "interactions" not in result.module_results:
            continue

        payload = _extract_interactions_payload(result.module_results)
        if not payload:
            continue

        version = _payload_semantics_version(payload)
        versioned_payloads.append((result, payload, version))

        session_rows.append(
            session_row_from_result(
                result,
                transcript_set,
                run_id=result.run_id,
                total_interactions=payload.get("total_interactions_count", 0),
                unique_speakers=payload.get("unique_speakers", 0),
                floor_equity_index=_equity_index(payload, "floor_equity_index"),
                interruption_asymmetry_index=_equity_index(
                    payload, "interruption_asymmetry_index"
                ),
                response_latency_fairness_index=_equity_index(
                    payload, "response_latency_fairness_index"
                ),
            )
        )

    if not session_rows:
        return None

    session_rows.sort(key=lambda row: row["order_index"])

    offending = [
        str(result.transcript_path)
        for result, _payload, version in versioned_payloads
        if version != INTERACTIONS_SEMANTICS_VERSION
    ]
    allow_directional_pool = not offending and bool(versioned_payloads)

    if offending:
        aggregation_warnings.append(
            build_warning(
                code="INTERACTIONS_SEMANTICS_VERSION_MISMATCH",
                message=(
                    "Skipped directional interactions pooling (role counts and "
                    "dominance-derived fields) because one or more runs use a "
                    f"missing or non-current semantics_version "
                    f"(current={INTERACTIONS_SEMANTICS_VERSION})."
                ),
                aggregation_key="interactions",
                transcripts_affected=offending,
                details={
                    "current_semantics_version": INTERACTIONS_SEMANTICS_VERSION,
                    "offending_transcripts": offending,
                },
            )
        )

    if allow_directional_pool:
        for result, payload, _version in versioned_payloads:
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
                        "canonical_speaker_id": canonical_id,
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

    speaker_rows: List[Dict[str, Any]] = []
    for aggregate in speaker_aggregates.values():
        count = aggregate["dominance_score_count"] or 1
        speaker_rows.append(
            {
                "canonical_speaker_id": aggregate["canonical_speaker_id"],
                "display_name": aggregate["display_name"],
                "interruptions_initiated": aggregate["interruptions_initiated"],
                "interruptions_received": aggregate["interruptions_received"],
                "responses_initiated": aggregate["responses_initiated"],
                "responses_received": aggregate["responses_received"],
                "dominance_score": aggregate["dominance_score_total"] / count,
            }
        )

    speakers_pooled: List[Dict[str, Any]] = []
    for aggregate in sorted(
        speaker_aggregates.values(), key=lambda a: a["canonical_speaker_id"]
    ):
        speakers_pooled.append(
            {
                "canonical_speaker_id": aggregate["canonical_speaker_id"],
                "display_name": aggregate["display_name"],
                "interruptions_initiated": aggregate["interruptions_initiated"],
                "interruptions_received": aggregate["interruptions_received"],
                "responses_initiated": aggregate["responses_initiated"],
                "responses_received": aggregate["responses_received"],
            }
        )
    interactions_pooled: Dict[str, Any] = {
        "schema_version": 1,
        "speakers": speakers_pooled,
    }

    out: Dict[str, Any] = {
        "session_rows": session_rows,
        "speaker_rows": speaker_rows,
        "interactions_pooled": interactions_pooled,
    }
    if aggregation_warnings:
        out["aggregation_warnings"] = aggregation_warnings
    return out
