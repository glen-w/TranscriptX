"""Transcript HTML rendering for export index pages."""

from __future__ import annotations

import html
from typing import Any

from transcriptx.export.grouping import group_contiguous_segments_by_speaker
from transcriptx.export.transcript_meta import (
    format_transcript_meta_bits,
    transcript_export_meta,
)
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
    meta = transcript_export_meta(transcript_data)
    meta_line = " · ".join(
        html.escape(str(bit)) for bit in format_transcript_meta_bits(meta)
    )

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
