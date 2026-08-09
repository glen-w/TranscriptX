"""Renderer-neutral chart grouping/order/title/meta preparation."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Callable, Optional, Sequence

from transcriptx.export.types import (
    ChartExportCard,
    ChartKind,
    ChartModuleGroup,
    ExportableItem,
)

ModuleOrderFn = Callable[[Sequence[str]], list[str]]
DescriptionFn = Callable[[object], Optional[str]]


def _default_order_modules(values: Sequence[str]) -> list[str]:
    return sorted(values, key=lambda value: (value.lower(), value))


def _sort_key(item: ExportableItem) -> tuple[str, str]:
    module = item.artifact.module or "Other"
    return (module.lower(), item.artifact.rel_path)


def sanitize_display_relpath(rel: Path | str) -> str:
    """Portable relative display path; never absolute run/staging paths."""
    text = rel.as_posix() if isinstance(rel, Path) else str(rel)
    text = text.replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    # Strip absolute / drive-letter / UNC forms down to a relative basename trail.
    if text.startswith("/") or (len(text) > 1 and text[1] == ":"):
        text = Path(text).name
    parts = [p for p in text.split("/") if p and p != ".."]
    return "/".join(parts) if parts else Path(text).name or "chart"


def module_anchor_id(module_name: str) -> str:
    return f"module-{module_name.lower().replace(' ', '-')}"


def chart_kind_for_artifact(kind: str | None) -> ChartKind:
    if kind == "chart_static":
        return "static"
    return "dynamic"


def prepare_chart_export_view(
    items: Sequence[ExportableItem],
    *,
    order_modules: Optional[ModuleOrderFn] = None,
    description_fn: Optional[DescriptionFn] = None,
) -> tuple[ChartModuleGroup, ...]:
    """Group and order chart items into renderer-neutral module groups."""
    order_fn = order_modules or _default_order_modules
    grouped: dict[str, list[ExportableItem]] = defaultdict(list)
    for item in sorted(items, key=_sort_key):
        grouped[item.artifact.module or "Other"].append(item)

    ordered_modules = order_fn(list(grouped.keys()))
    groups: list[ChartModuleGroup] = []
    for module_name in ordered_modules:
        cards: list[ChartExportCard] = []
        for item in grouped[module_name]:
            artifact = item.artifact
            title = artifact.title or Path(artifact.rel_path).name
            tags_s = ", ".join(sorted(artifact.tags)) if artifact.tags else "—"
            meta = (
                f"{artifact.module or '—'} · {artifact.scope or '—'} · "
                f"{artifact.kind} · {tags_s}"
            )
            description = item.description
            if description is None and description_fn is not None:
                try:
                    description = description_fn(artifact)
                except Exception:
                    description = None
            cards.append(
                ChartExportCard(
                    title=title,
                    meta=meta,
                    kind=chart_kind_for_artifact(artifact.kind),
                    description=description,
                    llm_description=item.llm_description,
                    source_path=item.source_path,
                    export_rel_path=item.export_rel_path,
                    display_relpath=sanitize_display_relpath(item.export_rel_path),
                )
            )
        groups.append(
            ChartModuleGroup(
                module_name=module_name,
                anchor_id=module_anchor_id(module_name),
                cards=tuple(cards),
            )
        )
    return tuple(groups)
