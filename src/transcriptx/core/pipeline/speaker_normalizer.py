"""
Group-level speaker identity normalization.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List

from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.speaker_extraction import get_unique_speakers
from transcriptx.io.transcript_service import TranscriptService

logger = get_logger()


@dataclass(frozen=True)
class CanonicalSpeakerMap:
    transcript_to_speakers: Dict[str, Dict[str, int]]
    canonical_to_display: Dict[int, str]
    transcript_to_display: Dict[str, Dict[str, str]]


def _fallback_canonical_id(label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def normalize_speakers_across_transcripts(
    per_transcript_results: List[PerTranscriptResult],
) -> CanonicalSpeakerMap:
    transcript_service = TranscriptService(enable_cache=True)
    transcript_to_speakers: Dict[str, Dict[str, int]] = {}
    canonical_to_display: Dict[int, str] = {}
    transcript_to_display: Dict[str, Dict[str, str]] = {}

    for result in per_transcript_results:
        segments = transcript_service.load_segments(
            result.transcript_path, use_cache=True
        )
        speaker_map = get_unique_speakers(segments)
        local_to_canonical: Dict[str, int] = {}
        local_to_display: Dict[str, str] = {}
        for local_id, display_name in speaker_map.items():
            local_id_str = str(local_id)
            canonical_id = _fallback_canonical_id(display_name or local_id_str)
            local_to_canonical[local_id_str] = canonical_id
            local_to_display[local_id_str] = display_name or local_id_str
            canonical_to_display.setdefault(canonical_id, display_name or local_id_str)
        transcript_to_speakers[result.transcript_path] = local_to_canonical
        transcript_to_display[result.transcript_path] = local_to_display

    return CanonicalSpeakerMap(
        transcript_to_speakers=transcript_to_speakers,
        canonical_to_display=canonical_to_display,
        transcript_to_display=transcript_to_display,
    )
