"""Export facade — delegates to existing zip helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from transcriptx.web.services import ArtifactService

if TYPE_CHECKING:
    from transcriptx.web.models.artifact import Artifact
    from transcriptx.utils.charts_export import ChartsExportResult


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
        from transcriptx.utils.charts_export import prepare_charts_export_zip

        return prepare_charts_export_zip(run_root, charts, run_id)
