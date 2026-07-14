"""TranscriptX export package — ZIP/HTML export for Overview and charts.

Public API for artifact and charts export. Prefer importing from this package;
``transcriptx.utils.export_*`` modules remain thin re-export shims for one release.
"""

from __future__ import annotations

from transcriptx.export.charts import (
    build_charts_index_html,
    export_rel_path_for_chart,
    generate_charts_index_html,
    prepare_charts_export_zip,
    render_chart_sections,
    resolve_exportable,
)
from transcriptx.export.grouping import group_contiguous_segments_by_speaker
from transcriptx.export.html_shell import (
    EXPORT_INDEX_CSS,
    omitted_charts_banner,
    wrap_export_page,
)
from transcriptx.export.index import (
    build_export_index_html,
    render_summaries_section,
    render_text_summary_section,
)
from transcriptx.export.markdown_html import summary_markdown_to_html
from transcriptx.export.paths import resolve_artifact_source_path
from transcriptx.export.resolve import (
    normalize_transcript_payload,
    resolve_export_llm_summary,
    resolve_export_page_title,
    resolve_export_text_summaries,
    resolve_export_transcript_data,
)
from transcriptx.export.transcript_html import render_transcript_section
from transcriptx.export.types import (
    HARD_CAP_BYTES,
    ChartsExportResult,
    ExportableItem,
    ExportTextSummary,
)

__all__ = [
    "HARD_CAP_BYTES",
    "ChartsExportResult",
    "ExportTextSummary",
    "ExportableItem",
    "EXPORT_INDEX_CSS",
    "build_charts_index_html",
    "build_export_index_html",
    "export_rel_path_for_chart",
    "generate_charts_index_html",
    "group_contiguous_segments_by_speaker",
    "normalize_transcript_payload",
    "omitted_charts_banner",
    "prepare_charts_export_zip",
    "render_chart_sections",
    "render_summaries_section",
    "render_text_summary_section",
    "render_transcript_section",
    "resolve_artifact_source_path",
    "resolve_export_llm_summary",
    "resolve_export_page_title",
    "resolve_export_text_summaries",
    "resolve_export_transcript_data",
    "resolve_exportable",
    "summary_markdown_to_html",
    "wrap_export_page",
]
