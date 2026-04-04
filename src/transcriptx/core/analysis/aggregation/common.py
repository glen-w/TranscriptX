"""Shared helpers for group aggregation modules."""

from __future__ import annotations

from typing import Any, Dict, List

from transcriptx.core.analysis.aggregation.rows import (
    _build_display_to_canonical,
    _fallback_canonical_id,
    _session_row_base,
)
from transcriptx.core.analysis.aggregation.warnings import build_warning
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def extract_payload(module_results: Dict[str, Any], module_name: str) -> Dict[str, Any]:
    result = module_results.get(module_name, {})
    if not isinstance(result, dict):
        return {}
    payload = result.get("payload") or result.get("results") or {}
    return payload if isinstance(payload, dict) else {}


def build_rows_from_stats(
    result: PerTranscriptResult,
    transcript_set: TranscriptSet,
    canonical_speaker_map: CanonicalSpeakerMap,
    global_stats: Dict[str, Any],
    speaker_stats: Dict[str, Any],
) -> Dict[str, Any]:
    session_row = _session_row_base(result, transcript_set)
    session_row.update(global_stats)
    display_to_canonical = _build_display_to_canonical(
        result.transcript_path, canonical_speaker_map
    )
    speaker_rows: List[Dict[str, Any]] = []
    for speaker, stats in speaker_stats.items():
        if not isinstance(stats, dict):
            continue
        canonical_id = display_to_canonical.get(
            speaker, _fallback_canonical_id(str(speaker))
        )
        row = {
            "canonical_speaker_id": canonical_id,
            "display_name": canonical_speaker_map.canonical_to_display.get(
                canonical_id, speaker
            ),
        }
        row.update(stats)
        speaker_rows.append(row)
    return {"session_rows": [session_row], "speaker_rows": speaker_rows}


def warning_payload_shape(agg_id: str, expected_keys: List[str]) -> Dict[str, Any]:
    return {
        "warning": build_warning(
            code="PAYLOAD_SHAPE_UNSUPPORTED",
            message=f"Expected keys missing: {', '.join(expected_keys)}",
            aggregation_key=agg_id,
            details={"missing_keys": expected_keys},
        )
    }
