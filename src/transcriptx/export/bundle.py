"""Selection-scoped resolved export bundle for HTML and EPUB indexes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from transcriptx.export.chart_prep import prepare_chart_export_view
from transcriptx.export.resolve import (
    resolve_export_page_title,
    resolve_export_text_summaries,
    resolve_export_transcript_data,
)
from transcriptx.export.types import ExportableItem, ResolvedExportBundle
from transcriptx.web.models.artifact import Artifact

ModuleOrderFn = Callable[[Sequence[str]], list[str]]
DescriptionFn = Callable[[Artifact], Optional[str]]
LlmDescriptionFn = Callable[[Artifact], Optional[str]]

_PRESENTATION_BASENAMES = frozenset({"index.html", "index.epub"})
_PRESENTATION_SUFFIXES = frozenset({".epub"})


def is_generated_presentation_artifact(
    *,
    rel_path: Path | str,
    artifact: Any = None,
) -> bool:
    """True for generated presentation products that must not feed resolvers."""
    rel = Path(rel_path)
    name = rel.name.lower()
    if name in _PRESENTATION_BASENAMES:
        return True
    if rel.suffix.lower() in _PRESENTATION_SUFFIXES:
        return True
    kind = getattr(artifact, "kind", None) if artifact is not None else None
    if kind in {"export_index_html", "export_index_epub", "export_epub"}:
        return True
    return False


def filter_copied_for_export_bundle(
    copied: Sequence[tuple[Artifact, Path]],
) -> list[tuple[Artifact, Path]]:
    """Drop generated presentation artifacts from the selection snapshot."""
    return [
        (artifact, rel)
        for artifact, rel in copied
        if not is_generated_presentation_artifact(rel_path=rel, artifact=artifact)
    ]


def resolve_export_bundle(
    *,
    staging_dir: Path,
    run_title: str,
    copied: Sequence[tuple[Artifact, Path]],
    run_root: Optional[Path] = None,
    order_modules: Optional[ModuleOrderFn] = None,
    description_fn: Optional[DescriptionFn] = None,
    llm_description_fn: Optional[LlmDescriptionFn] = None,
) -> ResolvedExportBundle:
    """Assemble selection-scoped inputs shared by HTML and EPUB Overview exports."""
    filtered = filter_copied_for_export_bundle(copied)

    transcript_data = resolve_export_transcript_data(
        staging_dir=staging_dir,
        run_root=run_root,
        copied=filtered,
    )
    text_summaries = resolve_export_text_summaries(
        staging_dir=staging_dir,
        copied=filtered,
    )
    page_title = resolve_export_page_title(
        staging_dir=staging_dir,
        run_root=run_root,
        fallback=run_title,
    )

    chart_items: list[ExportableItem] = []
    for artifact, rel in filtered:
        if artifact.kind not in {"chart_static", "chart_dynamic"}:
            continue
        description = None
        if description_fn is not None:
            try:
                description = description_fn(artifact)
            except Exception:
                description = None
        llm_description = None
        if llm_description_fn is not None:
            try:
                llm_description = llm_description_fn(artifact)
            except Exception:
                llm_description = None
        chart_items.append(
            ExportableItem(
                artifact=artifact,
                source_path=staging_dir / rel,
                export_rel_path=rel,
                size_bytes=0,
                description=description,
                llm_description=llm_description,
            )
        )

    chart_groups = prepare_chart_export_view(
        chart_items,
        order_modules=order_modules,
        description_fn=description_fn,
    )

    return ResolvedExportBundle(
        page_title=page_title,
        transcript_data=transcript_data,
        text_summaries=tuple(text_summaries),
        chart_items=tuple(chart_items),
        chart_groups=chart_groups,
    )
