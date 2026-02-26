"""
Group-level speaker identity normalization.

Runs once per group run and produces a frozen canonical speaker map.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Optional

from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.utils.speaker_extraction import get_unique_speakers
from transcriptx.io.transcript_service import TranscriptService
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


@dataclass(frozen=True)
class CanonicalSpeakerMap:
    """Frozen canonical speaker mapping for a group run."""

    transcript_to_speakers: Dict[str, Dict[str, int]]
    canonical_to_display: Dict[int, str]
    transcript_to_display: Dict[str, Dict[str, str]]


def _fallback_canonical_id(label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _lookup_transcript_file_id(transcript_key: str) -> Optional[int]:
    try:
        from transcriptx.database import get_session  # type: ignore[import]
        from transcriptx.database.models import TranscriptFile  # type: ignore[import]
    except Exception:
        return None

    session = get_session()
    try:
        record = (
            session.query(TranscriptFile)
            .filter(TranscriptFile.transcript_content_hash == transcript_key)
            .first()
        )
        return record.id if record else None
    finally:
        session.close()


def normalize_speakers_across_transcripts(
    per_transcript_results: List[PerTranscriptResult],
) -> CanonicalSpeakerMap:
    """
    Normalize speaker IDs across transcripts to canonical IDs.

    Runs once per group run. Returns frozen map for deterministic aggregation.
    """
    transcript_service = TranscriptService(enable_cache=True)

    identity_service = None
    try:
        from transcriptx.database.speaker_profiling import SpeakerIdentityService

        identity_service = SpeakerIdentityService()
    except Exception as e:
        logger.debug(f"SpeakerIdentityService unavailable: {e}")

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

        transcript_file_id = None
        if identity_service:
            transcript_file_id = _lookup_transcript_file_id(result.transcript_key)

        for local_id, display_name in speaker_map.items():
            local_id_str = str(local_id)

            canonical_id: Optional[int] = None
            if isinstance(local_id, int):
                canonical_id = local_id
            elif identity_service and transcript_file_id is not None:
                speaker_segments = [
                    seg
                    for seg in segments
                    if seg.get("speaker") == local_id
                    or seg.get("original_speaker_id") == local_id
                ]
                try:
                    speaker, _, _ = identity_service.resolve_speaker_identity(
                        diarized_label=local_id_str,
                        transcript_file_id=transcript_file_id,
                        session_data=speaker_segments,
                        confidence_threshold=0.7,
                    )
                    canonical_id = int(speaker.id)
                except Exception as e:
                    logger.debug(f"Speaker resolution failed for {local_id_str}: {e}")

            if canonical_id is None:
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
