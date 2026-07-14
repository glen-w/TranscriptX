"""Deprecated shim — import from ``transcriptx.export`` instead."""

from __future__ import annotations

from transcriptx.export.charts import (  # noqa: F401
    ChartsExportResult,
    ExportableItem,
    build_charts_index_html,
    export_rel_path_for_chart,
    generate_charts_index_html,
    prepare_charts_export_zip,
    render_chart_sections,
    resolve_exportable,
)
from transcriptx.export.html_shell import EXPORT_INDEX_CSS  # noqa: F401
from transcriptx.export.types import HARD_CAP_BYTES  # noqa: F401

# Private aliases kept for one-release compatibility with older imports/tests.
_ExportableItem = ExportableItem
_EXPORT_INDEX_CSS = EXPORT_INDEX_CSS
_export_rel_path_for_chart = export_rel_path_for_chart
_resolve_exportable = resolve_exportable

__all__ = [
    "HARD_CAP_BYTES",
    "ChartsExportResult",
    "ExportableItem",
    "EXPORT_INDEX_CSS",
    "build_charts_index_html",
    "export_rel_path_for_chart",
    "generate_charts_index_html",
    "prepare_charts_export_zip",
    "render_chart_sections",
    "resolve_exportable",
    "_ExportableItem",
    "_EXPORT_INDEX_CSS",
    "_export_rel_path_for_chart",
    "_resolve_exportable",
]
