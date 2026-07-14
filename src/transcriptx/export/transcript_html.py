"""Transcript HTML rendering for export index pages."""

from __future__ import annotations

import html
from typing import Any

from transcriptx.export.grouping import group_contiguous_segments_by_speaker
from transcriptx.utils.text_utils import format_time_detailed


def _format_timestamp_range(start: Any, end: Any) -> str:
    try:
        return (
            f"{format_time_detailed(float(start))} - {format_time_detailed(float(end))}"
        )
    except (TypeError, ValueError):
        return ""


def render_transcript_section(transcript_data: dict[str, Any]) -> str:
    """Render a basic transcript displayer section from transcript JSON.

    Mirrors the GUI segmented view: a metadata summary line followed by one block
    per contiguous speaker run (speaker chip, optional timestamp range, text).
    Every dynamic value is HTML-escaped.
    """
    segments = transcript_data.get("segments") or []
    metadata = transcript_data.get("metadata") or {}

    distinct_speakers: list[str] = []
    seen: set[str] = set()
    for segment in segments:
        speaker = segment.get("speaker_display") or segment.get("speaker")
        if speaker and speaker not in seen:
            seen.add(speaker)
            distinct_speakers.append(speaker)

    duration = metadata.get("duration")
    if duration is None and segments:
        try:
            duration = max(float(s.get("end", 0) or 0) for s in segments)
        except (TypeError, ValueError):
            duration = None

    meta_bits: list[str] = [
        f"{len(segments)} segments",
        f"{len(distinct_speakers)} speakers",
    ]
    if duration:
        try:
            meta_bits.append(f"Duration {format_time_detailed(float(duration))}")
        except (TypeError, ValueError):
            pass
    language = metadata.get("language")
    if language:
        meta_bits.append(f"Language: {language}")
    meta_line = " · ".join(html.escape(str(bit)) for bit in meta_bits)

    blocks: list[str] = []
    for speaker_name, group_segments in group_contiguous_segments_by_speaker(segments):
        group_start = group_segments[0].get("start", 0)
        group_end = group_segments[-1].get("end", 0)
        timestamp = _format_timestamp_range(group_start, group_end)
        time_html = (
            f'<span class="tx-time">{html.escape(timestamp)}</span>'
            if timestamp
            else ""
        )
        text_blocks = "".join(
            f'<p class="tx-text">{html.escape(str(segment.get("text", "")))}</p>'
            for segment in group_segments
            if str(segment.get("text", "")).strip()
        )
        blocks.append(
            '<div class="tx-segment">'
            f'<span class="tx-speaker-chip">{html.escape(speaker_name)}</span>'
            f"{time_html}"
            f"{text_blocks}"
            "</div>"
        )

    return (
        '<section id="transcript"><h2>Transcript</h2>'
        f'<p class="meta">{meta_line}</p>' + "".join(blocks) + "</section>"
    )
