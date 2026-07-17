"""Export facade — artifact ZIP and charts ZIP for the dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.web.services.artifact_service import ArtifactService

if TYPE_CHECKING:
    from transcriptx.export.types import ChartsExportResult
    from transcriptx.web.models.artifact import Artifact

logger = get_logger()


class ExportService:
    """UI-facing facade for Overview/Artifacts ZIP and charts-only ZIP."""

    @staticmethod
    def zip_artifacts(run_root: Path, artifact_ids: list[str]) -> Path | None:
        from transcriptx.export.zipping import assert_under_hard_cap, stage_copy_and_zip

        selected = ArtifactService._artifacts_for_export(run_root, artifact_ids)
        if not selected:
            return None
        total_bytes = sum(a.bytes for a in selected)
        assert_under_hard_cap(total_bytes)

        copy_pairs: list[tuple[Path, Path]] = []
        copied_meta: list[tuple[Artifact, Path]] = []
        for artifact in selected:
            path = ArtifactService.resolve_artifact_source_path(run_root, artifact)
            if path is None or not path.exists():
                continue
            prefix = Path(artifact.id[:16]) if artifact.storage_root else Path()
            rel = prefix / artifact.rel_path
            copy_pairs.append((path, rel))
            copied_meta.append((artifact, rel))

        def _write_index(staging_dir: Path) -> None:
            ExportService._write_export_index(
                staging_dir, run_root.name, copied_meta, run_root=run_root
            )

        result = stage_copy_and_zip(
            copy_pairs,
            zip_basename=f"{run_root.name}_export",
            write_index=_write_index,
            return_bytes=False,
            staging_prefix="transcriptx_export_",
        )
        assert isinstance(result, Path)
        return result

    @staticmethod
    def _write_export_index(
        staging_dir: Path,
        run_title: str,
        copied: List["tuple[Artifact, Path]"],
        *,
        run_root: Optional[Path] = None,
    ) -> None:
        """Write a self-contained ``index.html`` approximating the GUI.

        Renders a basic transcript displayer, optional module summaries, and an
        unfiltered charts gallery for the copied artifacts. Each section fails
        independently; the file is written when at least one section is produced and
        skipped only when none are. Never raises: index generation must not break
        the raw-file export.
        """
        try:
            from transcriptx.export import (
                ExportableItem,
                build_export_index_html,
                resolve_export_page_title,
                resolve_export_text_summaries,
                resolve_export_transcript_data,
            )
            from transcriptx.web.module_ui_groups import order_strings_like_modules
            from transcriptx.web.services.chart_view_model_service import (
                resolve_chart_display_description,
            )

            transcript_data = resolve_export_transcript_data(
                staging_dir=staging_dir,
                run_root=run_root,
                copied=copied,
            )
            text_summaries = resolve_export_text_summaries(
                staging_dir=staging_dir,
                copied=copied,
            )
            page_title = resolve_export_page_title(
                staging_dir=staging_dir,
                run_root=run_root,
                fallback=run_title,
            )

            chart_items: List[ExportableItem] = []
            for artifact, rel in copied:
                if artifact.kind in {"chart_static", "chart_dynamic"}:
                    description = None
                    try:
                        description = resolve_chart_display_description(artifact)
                    except Exception:
                        description = None
                    chart_items.append(
                        ExportableItem(
                            artifact=artifact,
                            source_path=staging_dir / rel,
                            export_rel_path=rel,
                            size_bytes=0,
                            description=description,
                        )
                    )

            html_payload = build_export_index_html(
                page_title=page_title,
                transcript_data=transcript_data,
                chart_items=chart_items,
                text_summaries=text_summaries,
                order_modules=order_strings_like_modules,
            )
            if html_payload:
                (staging_dir / "index.html").write_text(html_payload, encoding="utf-8")
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning("Failed to generate export index.html: %s", exc)

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
            order_modules=order_strings_like_modules,
            description_fn=resolve_chart_display_description,
        )
