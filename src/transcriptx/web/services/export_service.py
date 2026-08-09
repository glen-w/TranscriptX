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
        # Hard-cap gates selected source artifacts only; generated index.html /
        # index.epub presentation files are exempt (may re-embed static charts).
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
        """Write self-contained ``index.html`` and ``index.epub`` from one bundle.

        Generated presentation indexes are additive and non-fatal: failures must
        not break the raw-file ZIP export. Hard-cap does not include these files.
        """
        try:
            from transcriptx.export.bundle import resolve_export_bundle
            from transcriptx.export.epub import build_export_epub
            from transcriptx.export.index import build_export_index_html
            from transcriptx.web.module_ui_groups import order_strings_like_modules
            from transcriptx.web.services.chart_view_model_service import (
                resolve_chart_display_description,
            )
            from transcriptx.web.services.chart_llm_description import (
                resolve_chart_llm_description,
            )

            def _llm_desc(artifact: Artifact) -> str | None:
                return resolve_chart_llm_description(run_root, artifact)

            bundle = resolve_export_bundle(
                staging_dir=staging_dir,
                run_title=run_title,
                copied=copied,
                run_root=run_root,
                order_modules=order_strings_like_modules,
                description_fn=resolve_chart_display_description,
                llm_description_fn=_llm_desc if run_root is not None else None,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning("Failed to resolve export bundle: %s", exc)
            return

        try:
            html_payload = build_export_index_html(
                page_title=bundle.page_title,
                transcript_data=bundle.transcript_data,
                chart_items=list(bundle.chart_items),
                chart_groups=bundle.chart_groups,
                text_summaries=bundle.text_summaries,
            )
            if html_payload:
                (staging_dir / "index.html").write_text(html_payload, encoding="utf-8")
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning("Failed to generate export index.html: %s", exc)

        try:
            build_export_epub(
                output_path=staging_dir / "index.epub",
                bundle=bundle,
                page_title=bundle.page_title,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning("Failed to generate export index.epub: %s", exc)

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
        from transcriptx.web.services.chart_llm_description import (
            resolve_chart_llm_description,
        )

        return prepare_charts_export_zip(
            run_root,
            charts,
            run_id,
            order_modules=order_strings_like_modules,
            description_fn=resolve_chart_display_description,
            llm_description_fn=lambda a: resolve_chart_llm_description(run_root, a),
        )
