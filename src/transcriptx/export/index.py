"""Build combined Overview-export index HTML pages."""

from __future__ import annotations

import html
from typing import Any, Callable, Optional, Sequence

from transcriptx.export.charts import render_chart_sections
from transcriptx.export.html_shell import omitted_charts_banner, wrap_export_page
from transcriptx.export.markdown_html import summary_markdown_to_html
from transcriptx.export.resolve import normalize_transcript_payload
from transcriptx.export.transcript_html import render_transcript_section
from transcriptx.export.types import ExportTextSummary, ExportableItem

ModuleOrderFn = Callable[[Sequence[str]], list[str]]


def _is_speaker_summary(summary: ExportTextSummary) -> bool:
    title = str(summary.get("title") or "")
    section_id = str(summary.get("section_id") or "")
    return (
        title.startswith("Speaker Summary")
        or "llm_speaker_summary" in section_id
        or "llm-speaker-summary" in section_id
    )


def _nav_heading(label: str) -> str:
    return f'<li class="nav-heading"><strong>{html.escape(label)}</strong></li>'


def render_summaries_section(summaries: Sequence[ExportTextSummary]) -> str:
    """Render grouped summary blocks for the export index page."""
    general = [s for s in summaries if not _is_speaker_summary(s)]
    speakers = [s for s in summaries if _is_speaker_summary(s)]
    parts: list[str] = []
    if general:
        blocks = "".join(render_text_summary_section(summary) for summary in general)
        parts.append(f'<section id="summaries"><h2>Summaries</h2>{blocks}</section>')
    if speakers:
        blocks = "".join(render_text_summary_section(summary) for summary in speakers)
        parts.append(
            f'<section id="speaker-summaries"><h2>Speaker Summaries</h2>{blocks}</section>'
        )
    return "".join(parts)


def render_text_summary_section(summary: ExportTextSummary) -> str:
    """Render a prose summary block for the export index page."""
    section_id = summary.get("section_id") or "summary"
    title = summary.get("title") or "Summary"
    body = summary.get("body") or ""
    provenance = summary.get("provenance") or {}

    meta_bits: list[str] = []
    model = provenance.get("model")
    provider = provenance.get("provider")
    if model:
        meta_bits.append(f"Model: {model}")
    if provider:
        meta_bits.append(f"Provider: {provider}")
    if provenance.get("truncated"):
        meta_bits.append("Input truncated")

    meta_html = ""
    if meta_bits:
        meta_line = " · ".join(html.escape(str(bit)) for bit in meta_bits)
        meta_html = f'<p class="meta">{meta_line}</p>'

    body_html = summary_markdown_to_html(str(body))
    if not body_html:
        body_html = f"<p>{html.escape(str(body))}</p>" if str(body).strip() else ""

    return (
        f'<section id="{html.escape(section_id)}">'
        f"<h2>{html.escape(title)}</h2>"
        f'<div class="tx-summary"><div class="tx-summary-body">{body_html}</div></div>'
        f"{meta_html}"
        "</section>"
    )


def _render_included_files(included_files: Sequence[str]) -> str:
    items = "".join(f"<li>{html.escape(path)}</li>" for path in sorted(included_files))
    return (
        '<section id="included-files" class="included-files">'
        "<h2>Included files</h2><ul>" + items + "</ul></section>"
    )


def build_export_index_html(
    *,
    page_title: str,
    transcript_data: Optional[dict[str, Any]] = None,
    chart_items: Optional[list[ExportableItem]] = None,
    text_summaries: Optional[Sequence[ExportTextSummary]] = None,
    llm_summary: Optional[ExportTextSummary] = None,
    omitted_count: int = 0,
    included_files: Optional[Sequence[str]] = None,
    order_modules: Optional[ModuleOrderFn] = None,
) -> Optional[str]:
    """Build the combined Overview-export ``index.html``.

    Renders a transcript section, optional summaries, and/or a charts gallery
    section. Each section is produced independently; a failure in one does not drop
    the others. Returns ``None`` when no section could be produced (the caller
    then skips writing the file).
    """
    transcript_section: Optional[str] = None
    normalized_transcript = normalize_transcript_payload(transcript_data)
    if normalized_transcript is not None:
        try:
            transcript_section = render_transcript_section(normalized_transcript)
        except Exception:
            transcript_section = None

    summary_items: list[ExportTextSummary] = []
    if text_summaries:
        summary_items.extend(
            summary for summary in text_summaries if summary.get("body")
        )
    elif llm_summary and llm_summary.get("body"):
        summary_items.append(llm_summary)

    summaries_section: Optional[str] = None
    if summary_items:
        try:
            summaries_section = render_summaries_section(summary_items)
        except Exception:
            summaries_section = None

    chart_toc: list[str] = []
    chart_sections: list[str] = []
    if chart_items:
        try:
            chart_toc, chart_sections = render_chart_sections(
                chart_items, order_modules=order_modules
            )
        except Exception:
            chart_toc, chart_sections = [], []

    has_transcript = transcript_section is not None
    has_summaries = summaries_section is not None
    has_charts = bool(chart_sections)
    if not has_transcript and not has_summaries and not has_charts:
        return None

    nav_entries: list[str] = []
    if has_transcript:
        nav_entries.append('<li><a href="#transcript">Transcript</a></li>')
    if has_summaries and summary_items:
        general_summaries = [s for s in summary_items if not _is_speaker_summary(s)]
        speaker_summaries = [s for s in summary_items if _is_speaker_summary(s)]
        if general_summaries:
            nav_entries.append(_nav_heading("Summaries"))
            for summary in general_summaries:
                section_id = summary.get("section_id") or "summary"
                title = summary.get("title") or "Summary"
                nav_entries.append(
                    f'<li><a href="#{html.escape(section_id)}">'
                    f"{html.escape(title)}</a></li>"
                )
        if speaker_summaries:
            nav_entries.append(_nav_heading("Speaker Summaries"))
            for summary in speaker_summaries:
                section_id = summary.get("section_id") or "summary"
                title = summary.get("title") or "Speaker Summary"
                nav_entries.append(
                    f'<li><a href="#{html.escape(section_id)}">'
                    f"{html.escape(title)}</a></li>"
                )
    if has_charts:
        nav_entries.append(_nav_heading("Charts"))
        nav_entries.extend(chart_toc)

    body_sections: list[str] = []
    if has_transcript and transcript_section is not None:
        body_sections.append(transcript_section)
    if has_summaries and summaries_section is not None:
        body_sections.append(summaries_section)
    body_sections.extend(chart_sections)
    if included_files:
        body_sections.append(_render_included_files(included_files))

    content = omitted_charts_banner(omitted_count) + "".join(body_sections)
    return wrap_export_page(page_title, "".join(nav_entries), content)
