"""
Shared helpers for building canonical group aggregation rows.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict

from transcriptx.core.analysis.aggregation.schema import get_transcript_id
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _fallback_canonical_id(label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


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


def _session_row_base(
    result: PerTranscriptResult, transcript_set: TranscriptSet
) -> Dict[str, Any]:
    return {
        "transcript_id": get_transcript_id(result, transcript_set),
        "order_index": result.order_index,
        "run_relpath": result.output_dir,
    }


def session_row_from_result(
    result: PerTranscriptResult, transcript_set: TranscriptSet, **extra: Any
) -> Dict[str, Any]:
    row = _session_row_base(result, transcript_set)
    row.update(extra)
    return row
