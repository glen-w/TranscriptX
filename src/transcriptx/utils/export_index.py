"""Deprecated shim — import from ``transcriptx.export`` instead."""

from __future__ import annotations

from transcriptx.export.index import (  # noqa: F401
    build_export_index_html,
    render_summaries_section,
    render_text_summary_section,
)
from transcriptx.export.resolve import (  # noqa: F401
    normalize_transcript_payload,
    resolve_export_llm_summary,
    resolve_export_page_title,
    resolve_export_text_summaries,
    resolve_export_transcript_data,
)
from transcriptx.export.transcript_html import render_transcript_section  # noqa: F401
from transcriptx.export.types import ExportTextSummary  # noqa: F401

__all__ = [
    "ExportTextSummary",
    "build_export_index_html",
    "normalize_transcript_payload",
    "render_summaries_section",
    "render_text_summary_section",
    "render_transcript_section",
    "resolve_export_llm_summary",
    "resolve_export_page_title",
    "resolve_export_text_summaries",
    "resolve_export_transcript_data",
]
