"""View-model helpers for charts page orchestration."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from transcriptx.core.utils.chart_registry import (
    get_chart_definition,
    get_chart_registry,
    get_default_group_overview_charts,
    get_default_overview_charts,
    select_preferred_artifacts,
)
from transcriptx.web.models.artifact import Artifact, ArtifactFilters


def compute_chart_badges(all_charts: List[Artifact]) -> List[str]:
    st_c = sum(1 for a in all_charts if a.kind == "chart_static")
    dyn_c = sum(1 for a in all_charts if a.kind == "chart_dynamic")
    badge_bits: List[str] = []
    if all_charts:
        badge_bits.append(f"{len(all_charts)} charts")
        if st_c:
            badge_bits.append(f"Static {st_c}")
        if dyn_c:
            badge_bits.append(f"Dynamic {dyn_c}")
    return badge_bits


def build_filter_options(
    all_charts: List[Artifact],
) -> Tuple[List[str], List[str], List[str], List[str]]:
    modules = sorted({a.module for a in all_charts if a.module})
    scopes = sorted({a.scope for a in all_charts if a.scope})
    tags = sorted({tag for a in all_charts for tag in a.tags})
    subviews = sorted({a.subview for a in all_charts if a.subview})
    return modules, scopes, tags, subviews


def apply_chart_filters(
    all_charts: List[Artifact],
    *,
    module: str | None,
    scope: str | None,
    kind: str | None,
    tags: List[str] | None,
    subview: str | None,
    slice_id: str | None,
) -> List[Artifact]:
    if kind == "__none__":
        return []
    flt = ArtifactFilters(
        module=module,
        scope=scope,
        kind=kind,
        tags=tags or None,
        subview=subview,
        slice_id=slice_id,
    )
    return [a for a in all_charts if flt.matches(a)]


def build_overview_slots(
    overview_candidates: List[Artifact],
    user_overview: List[str],
    missing_behavior: str,
    max_items: int | None,
) -> List[Dict[str, Any]]:
    registry = get_chart_registry()
    if user_overview:
        enabled_viz_ids = user_overview
    elif any("group_aggregate" in a.tags for a in overview_candidates):
        enabled_viz_ids = get_default_group_overview_charts()
    else:
        enabled_viz_ids = get_default_overview_charts()
    if isinstance(max_items, int) and max_items > 0:
        enabled_viz_ids = enabled_viz_ids[:max_items]

    slots: List[Dict[str, Any]] = []
    for viz_id in enabled_viz_ids:
        chart_def = registry.get(viz_id)
        if not chart_def:
            if missing_behavior == "show_placeholder":
                slots.append(
                    {
                        "label": f"{viz_id} (not available)",
                        "viz_id": viz_id,
                        "artifacts": [],
                        "missing": True,
                    }
                )
            continue
        cd = get_chart_definition(viz_id)
        matching = (
            select_preferred_artifacts(
                [a for a in overview_candidates if cd and cd.match.matches(a, cd)],
                cd,
            )
            if cd
            else []
        )
        if matching or missing_behavior == "show_placeholder":
            display_title = (
                matching[0].title if matching and matching[0].title else chart_def.label
            )
            slots.append(
                {
                    "label": display_title,
                    "viz_id": viz_id,
                    "artifacts": matching,
                    "cardinality": chart_def.cardinality,
                    "missing": not matching,
                }
            )
    return slots
