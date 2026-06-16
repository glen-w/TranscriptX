"""
Combined Overview-export index page builder.

Builds a single self-contained ``index.html`` for the Overview artifact export
that approximates the GUI: a basic server-rendered transcript displayer plus an
unfiltered charts gallery (all charts in the selection). Rendering is done
server-side (not client-side JS) so the page works when opened directly from
disk over ``file://``, where browsers block ``fetch()`` of local JSON.

The transcript and charts sections fail independently: a malformed transcript
drops only the transcript section, and a charts render failure drops only the
gallery. ``build_export_index_html`` returns ``None`` only when neither section
could be produced, so the caller can skip writing the file entirely.
"""

from __future__ import annotations

import html
from typing import Any, Optional, Sequence

from transcriptx.utils.charts_export import (
    _EXPORT_INDEX_CSS,
    _ExportableItem,
    render_chart_sections,
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

    Mirrors the GUI plain view: a metadata summary line followed by one block
    per segment (speaker chip, optional timestamp range, text). Every dynamic
    value is HTML-escaped.
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
    for segment in segments:
        speaker = segment.get("speaker_display") or segment.get("speaker") or "Unknown"
        text = str(segment.get("text", ""))
        timestamp = _format_timestamp_range(
            segment.get("start", 0), segment.get("end", 0)
        )
        time_html = (
            f'<span class="tx-time">{html.escape(timestamp)}</span>'
            if timestamp
            else ""
        )
        blocks.append(
            '<div class="tx-segment">'
            f'<span class="tx-speaker-chip">{html.escape(str(speaker))}</span>'
            f"{time_html}"
            f'<p class="tx-text">{html.escape(text)}</p>'
            "</div>"
        )

    return (
        '<section id="transcript"><h2>Transcript</h2>'
        f'<p class="meta">{meta_line}</p>' + "".join(blocks) + "</section>"
    )


def _render_included_files(included_files: Sequence[str]) -> str:
    items = "".join(f"<li>{html.escape(path)}</li>" for path in sorted(included_files))
    return (
        '<section id="included-files" class="included-files">'
        "<h2>Included files</h2><ul>" + items + "</ul></section>"
    )


def build_export_index_html(
    *,
    run_title: str,
    transcript_data: Optional[dict[str, Any]] = None,
    chart_items: Optional[list[_ExportableItem]] = None,
    omitted_count: int = 0,
    included_files: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """Build the combined Overview-export ``index.html``.

    Renders a transcript section and/or a charts gallery section. Each section is
    produced independently; a failure in one does not drop the other. Returns
    ``None`` when neither section could be produced (the caller then skips
    writing the file).
    """
    transcript_section: Optional[str] = None
    if transcript_data:
        try:
            transcript_section = render_transcript_section(transcript_data)
        except Exception:
            transcript_section = None

    chart_toc: list[str] = []
    chart_sections: list[str] = []
    if chart_items:
        try:
            chart_toc, chart_sections = render_chart_sections(chart_items)
        except Exception:
            chart_toc, chart_sections = [], []

    has_transcript = transcript_section is not None
    has_charts = bool(chart_sections)
    if not has_transcript and not has_charts:
        return None

    nav_entries: list[str] = []
    if has_transcript:
        nav_entries.append('<li><a href="#transcript">Transcript</a></li>')
    if has_charts:
        nav_entries.append("<li><strong>Charts</strong></li>")
        nav_entries.extend(chart_toc)

    omitted_banner = ""
    if omitted_count > 0:
        plural = "s" if omitted_count != 1 else ""
        omitted_banner = (
            '<div class="notice">'
            f"{omitted_count} chart{plural} were unavailable and omitted from this export."
            "</div>"
        )

    body_sections: list[str] = []
    if has_transcript and transcript_section is not None:
        body_sections.append(transcript_section)
    body_sections.extend(chart_sections)
    if included_files:
        body_sections.append(_render_included_files(included_files))

    return (
        "<!DOCTYPE html>"
        "<html><head><meta charset='utf-8'/>"
        f"<title>Export - {html.escape(run_title)}</title>"
        "<style>" + _EXPORT_INDEX_CSS + "</style></head><body>"
        "<main><nav><strong>Contents</strong><ul>"
        + "".join(nav_entries)
        + "</ul></nav><div class='content'>"
        f"<h1>Export: {html.escape(run_title)}</h1>"
        + omitted_banner
        + "".join(body_sections)
        + "</div></main></body></html>"
    )
