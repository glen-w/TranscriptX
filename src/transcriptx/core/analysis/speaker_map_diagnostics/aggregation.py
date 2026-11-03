"""Group aggregation for speaker_map_diagnostics (B19)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.aggregation.rows import _session_row_base
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult


def _extract_payload(module_results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw = module_results.get("speaker_map_diagnostics")
    if not isinstance(raw, dict):
        return None
    if "speaker_tier" in raw or "semantic_version" in raw:
        return raw
    nested = raw.get("results") or raw.get("payload")
    if isinstance(nested, dict) and (
        "speaker_tier" in nested or "semantic_version" in nested
    ):
        return nested
    return raw


def aggregate_speaker_map_diagnostics(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: Any,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """Per-session speaker-tier honesty; no speaker pooling."""
    del canonical_speaker_map
    session_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results)
        if not payload:
            continue
        row = _session_row_base(result, transcript_set)
        row.update(
            {
                "status": payload.get("status"),
                "speaker_tier": payload.get("speaker_tier"),
                "named_speaker_count": payload.get("named_speaker_count"),
                "unique_label_count": payload.get("unique_label_count"),
                "has_sidecar": payload.get("has_sidecar"),
            }
        )
        session_rows.append(row)
    if not session_rows:
        return None
    return {"session_rows": session_rows, "speaker_rows": []}
