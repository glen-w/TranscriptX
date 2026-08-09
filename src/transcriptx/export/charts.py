"""Charts gallery export helpers."""

from __future__ import annotations

from pathlib import Path
import html
from typing import Callable, Optional, Sequence

from transcriptx.export.chart_prep import prepare_chart_export_view
from transcriptx.export.html_shell import omitted_charts_banner, wrap_export_page
from transcriptx.export.paths import resolve_artifact_source_path
from transcriptx.export.types import (
    HARD_CAP_BYTES,
    ChartModuleGroup,
    ChartsExportResult,
    ExportableItem,
)
from transcriptx.export.zipping import assert_under_hard_cap, stage_copy_and_zip
from transcriptx.web.models.artifact import Artifact

PathResolver = Callable[[Path, Artifact], Optional[Path]]
ModuleOrderFn = Callable[[Sequence[str]], list[str]]
DescriptionFn = Callable[[Artifact], Optional[str]]
LlmDescriptionFn = Callable[[Artifact], Optional[str]]


def export_rel_path_for_chart(artifact: Artifact) -> Path:
    if artifact.storage_root:
        return Path(artifact.id[:16]) / artifact.rel_path
    return Path(artifact.rel_path)


def resolve_exportable(
    run_root: Path,
    charts: list[Artifact],
    *,
    resolve_path: Optional[PathResolver] = None,
    description_fn: Optional[DescriptionFn] = None,
    llm_description_fn: Optional[LlmDescriptionFn] = None,
) -> list[ExportableItem]:
    resolver = resolve_path or resolve_artifact_source_path
    items: list[ExportableItem] = []
    for artifact in charts:
        source = resolver(run_root, artifact)
        if source is None:
            continue
        try:
            size_bytes = source.stat().st_size
        except OSError:
            size_bytes = int(artifact.bytes or 0)
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
        items.append(
            ExportableItem(
                artifact=artifact,
                source_path=source,
                export_rel_path=export_rel_path_for_chart(artifact),
                size_bytes=size_bytes,
                description=description,
                llm_description=llm_description,
            )
        )
    return items


def render_chart_sections_from_groups(
    groups: Sequence[ChartModuleGroup],
) -> tuple[list[str], list[str]]:
    """Render prepared chart groups to TOC entries and section HTML."""
    toc_entries: list[str] = []
    section_html: list[str] = []
    for group in groups:
        toc_entries.append(
            f'<li><a href="#{html.escape(group.anchor_id, quote=True)}">'
            f"{html.escape(group.module_name)}</a></li>"
        )
        cards: list[str] = []
        for card in group.cards:
            rel = card.export_rel_path.as_posix()
            if card.kind == "static":
                body = (
                    f'<a class="chart-thumb" href="{html.escape(rel, quote=True)}" '
                    f'title="Open {html.escape(card.title, quote=True)}">'
                    f'<img src="{html.escape(rel, quote=True)}" '
                    f'alt="{html.escape(card.title, quote=True)}" loading="lazy" />'
                    "</a>"
                )
            else:
                body = (
                    '<span class="badge">Interactive HTML</span>'
                    f'<a class="open-link" href="{html.escape(rel, quote=True)}">'
                    "Open chart</a>"
                    f'<iframe title="{html.escape(card.title, quote=True)}" '
                    f'src="{html.escape(rel, quote=True)}"></iframe>'
                    '<p class="hint">Inline preview is best effort for local files.</p>'
                )
            description_html = ""
            if card.description:
                description_html = (
                    f'<p class="chart-desc">{html.escape(card.description)}</p>'
                )
            llm_html = ""
            if card.llm_description:
                llm_html = (
                    f'<p class="chart-narrative">'
                    f"{html.escape(card.llm_description)}</p>"
                )
            cards.append(
                '<article class="card">'
                f"<h3>{html.escape(card.title)}</h3>"
                f'<p class="meta">{html.escape(card.meta)}</p>'
                f"{description_html}"
                f"{body}"
                f"{llm_html}"
                "</article>"
            )
        section_html.append(
            f'<section id="{html.escape(group.anchor_id, quote=True)}">'
            f"<h2>{html.escape(group.module_name)}</h2>"
            '<div class="card-grid">' + "".join(cards) + "</div></section>"
        )
    return toc_entries, section_html


def render_chart_sections(
    items: list[ExportableItem],
    *,
    order_modules: Optional[ModuleOrderFn] = None,
    description_fn: Optional[DescriptionFn] = None,
) -> tuple[list[str], list[str]]:
    """Build the per-module TOC entries and chart gallery ``<section>`` markup.

    Returns a tuple of (toc_entries, section_html). Shared by the charts-only
    export index and the combined Overview export index.
    """
    groups = prepare_chart_export_view(
        items,
        order_modules=order_modules,
        description_fn=description_fn,
    )
    return render_chart_sections_from_groups(groups)


def build_charts_index_html(
    items: list[ExportableItem],
    omitted_count: int,
    run_title: str,
    *,
    order_modules: Optional[ModuleOrderFn] = None,
    description_fn: Optional[DescriptionFn] = None,
) -> str:
    toc_entries, section_html = render_chart_sections(
        items,
        order_modules=order_modules,
        description_fn=description_fn,
    )
    content = omitted_charts_banner(omitted_count) + "".join(section_html)
    return wrap_export_page(
        f"Charts Export - {run_title}",
        "".join(toc_entries),
        content,
        nav_label="Modules",
        heading=f"Charts Export: {run_title}",
    )


# Backward-compatible alias used by older call sites / tests.
generate_charts_index_html = build_charts_index_html


def prepare_charts_export_zip(
    run_root: Path,
    charts: list[Artifact],
    run_id: str,
    *,
    resolve_path: Optional[PathResolver] = None,
    order_modules: Optional[ModuleOrderFn] = None,
    description_fn: Optional[DescriptionFn] = None,
    llm_description_fn: Optional[LlmDescriptionFn] = None,
    hard_cap_bytes: Optional[int] = None,
) -> ChartsExportResult:
    items = resolve_exportable(
        run_root,
        charts,
        resolve_path=resolve_path,
        description_fn=description_fn,
        llm_description_fn=llm_description_fn,
    )
    omitted_count = max(0, len(charts) - len(items))
    total_bytes = sum(item.size_bytes for item in items)
    # Resolve at call time so tests can monkeypatch module-level HARD_CAP_BYTES.
    cap = HARD_CAP_BYTES if hard_cap_bytes is None else hard_cap_bytes
    assert_under_hard_cap(total_bytes, hard_cap=cap)

    def _write_index(staging_dir: Path) -> None:
        index_html = build_charts_index_html(
            items,
            omitted_count,
            run_id,
            order_modules=order_modules,
            description_fn=description_fn,
        )
        (staging_dir / "index.html").write_text(index_html, encoding="utf-8")

    payload = stage_copy_and_zip(
        [(item.source_path, item.export_rel_path) for item in items],
        zip_basename=f"{run_id}_charts",
        write_index=_write_index,
        return_bytes=True,
        staging_prefix="tx_charts_export_",
        zip_temp_prefix="tx_charts_zip_",
    )
    assert isinstance(payload, bytes)

    module_names = {item.artifact.module or "Other" for item in items}
    return ChartsExportResult(
        bytes=payload,
        filename=f"{run_id}_charts.zip",
        exported_count=len(items),
        omitted_count=omitted_count,
        module_count=len(module_names),
    )
