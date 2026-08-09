"""TranscriptX export package — ZIP/HTML/EPUB export for Overview and charts.

Public API for artifact and charts export. Import from this package.
"""

from __future__ import annotations

from transcriptx.export.bundle import (
    filter_copied_for_export_bundle,
    is_generated_presentation_artifact,
    resolve_export_bundle,
)
from transcriptx.export.chart_prep import (
    prepare_chart_export_view,
    sanitize_display_relpath,
)
from transcriptx.export.charts import (
    build_charts_index_html,
    export_rel_path_for_chart,
    generate_charts_index_html,
    prepare_charts_export_zip,
    render_chart_sections,
    render_chart_sections_from_groups,
    resolve_exportable,
)
from transcriptx.export.epub import build_export_epub, plan_export_epub
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
from transcriptx.export.transcript_meta import (
    format_transcript_meta_bits,
    transcript_export_meta,
)
from transcriptx.export.types import (
    HARD_CAP_BYTES,
    ChartExportCard,
    ChartModuleGroup,
    ChartsExportResult,
    ExportableItem,
    ExportTextSummary,
    ResolvedExportBundle,
    TranscriptExportMeta,
)

__all__ = [
    "HARD_CAP_BYTES",
    "ChartExportCard",
    "ChartModuleGroup",
    "ChartsExportResult",
    "ExportTextSummary",
    "ExportableItem",
    "EXPORT_INDEX_CSS",
    "ResolvedExportBundle",
    "TranscriptExportMeta",
    "build_charts_index_html",
    "build_export_epub",
    "build_export_index_html",
    "export_rel_path_for_chart",
    "filter_copied_for_export_bundle",
    "format_transcript_meta_bits",
    "generate_charts_index_html",
    "group_contiguous_segments_by_speaker",
    "is_generated_presentation_artifact",
    "normalize_transcript_payload",
    "omitted_charts_banner",
    "plan_export_epub",
    "prepare_chart_export_view",
    "prepare_charts_export_zip",
    "render_chart_sections",
    "render_chart_sections_from_groups",
    "render_summaries_section",
    "render_text_summary_section",
    "render_transcript_section",
    "resolve_artifact_source_path",
    "resolve_export_bundle",
    "resolve_export_llm_summary",
    "resolve_export_page_title",
    "resolve_export_text_summaries",
    "resolve_export_transcript_data",
    "resolve_exportable",
    "sanitize_display_relpath",
    "summary_markdown_to_html",
    "transcript_export_meta",
    "wrap_export_page",
]
