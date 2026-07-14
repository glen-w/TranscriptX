"""Export facade — delegates to existing zip helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from transcriptx.web.services import ArtifactService

if TYPE_CHECKING:
    from transcriptx.export.types import ChartsExportResult
    from transcriptx.web.models.artifact import Artifact


class ExportService:
    """Thin facade over artifact and charts export utilities."""

    @staticmethod
    def zip_artifacts(run_root: Path, artifact_ids: list[str]) -> Path | None:
        return ArtifactService.zip_artifacts(run_root, artifact_ids)

    @staticmethod
    def zip_charts(
        run_root: Path,
        charts: list[Artifact],
        run_id: str,
    ) -> ChartsExportResult:
        from transcriptx.export.charts import prepare_charts_export_zip
        from transcriptx.web.module_ui_groups import order_strings_like_modules
        from transcriptx.web.services.chart_view_model_service import (
            resolve_chart_display_description,
        )

        return prepare_charts_export_zip(
            run_root,
            charts,
            run_id,
            resolve_path=ArtifactService.resolve_artifact_source_path,
            order_modules=order_strings_like_modules,
            description_fn=resolve_chart_display_description,
        )
