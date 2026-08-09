"""Shared transcript metadata for HTML and EPUB export indexes."""

from __future__ import annotations

from typing import Any

from transcriptx.export.types import TranscriptExportMeta
from transcriptx.utils.text_utils import format_time_detailed


def transcript_export_meta(transcript_data: dict[str, Any]) -> TranscriptExportMeta:
    """Derive segment/speaker/duration/language metadata from normalized transcript."""
    segments = transcript_data.get("segments") or []
    metadata = transcript_data.get("metadata") or {}

    distinct_speakers: list[str] = []
    seen: set[str] = set()
    for segment in segments:
        speaker = segment.get("speaker_display") or segment.get("speaker")
        if speaker and speaker not in seen:
            seen.add(speaker)
            distinct_speakers.append(str(speaker))

    duration = metadata.get("duration")
    if duration is None and segments:
        try:
            duration = max(float(s.get("end", 0) or 0) for s in segments)
        except (TypeError, ValueError):
            duration = None
    else:
        try:
            duration = float(duration) if duration is not None else None
        except (TypeError, ValueError):
            duration = None

    language = metadata.get("language")
    language_s = str(language) if language else None

    return TranscriptExportMeta(
        segment_count=len(segments),
        speakers=tuple(distinct_speakers),
        duration_seconds=duration,
        language=language_s,
    )


def format_transcript_meta_bits(meta: TranscriptExportMeta) -> list[str]:
    """Human-readable meta line fragments (unescaped)."""
    bits: list[str] = [
        f"{meta.segment_count} segments",
        f"{len(meta.speakers)} speakers",
    ]
    if meta.duration_seconds:
        try:
            bits.append(f"Duration {format_time_detailed(float(meta.duration_seconds))}")
        except (TypeError, ValueError):
            pass
    if meta.language:
        bits.append(f"Language: {meta.language}")
    return bits
