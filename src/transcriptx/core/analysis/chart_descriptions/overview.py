"""Pure core overview chart selection (no web / Streamlit imports)."""

from __future__ import annotations

from typing import Any, Protocol, Sequence

from transcriptx.core.analysis.chart_descriptions.inventory import (
    LogicalChartDescriptor,
)
from transcriptx.core.utils.chart_registry import (
    get_chart_registry,
    get_default_group_overview_charts,
    get_default_overview_charts,
)


class OverviewChartLike(Protocol):
    """Minimal protocol for overview matching (neutral descriptors)."""

    viz_id: str


def resolve_overview_viz_ids(
    *,
    run_kind: str,
    user_overview: Sequence[str] | None,
    max_items: int | None,
    overview_enabled: bool = True,
) -> list[str]:
    """Effective dashboard overview viz_ids from config + registry defaults.

    When ``overview_enabled`` is False, returns an empty list (no Overview strip).
    Unknown user-configured viz_ids are preserved so callers can show placeholders.
    """
    if not overview_enabled:
        return []
    if user_overview:
        enabled = list(user_overview)
    elif run_kind == "group":
        enabled = list(get_default_group_overview_charts())
    else:
        enabled = list(get_default_overview_charts())
    if isinstance(max_items, int) and max_items > 0:
        enabled = enabled[:max_items]
    return enabled


def select_overview_descriptors(
    charts: Sequence[LogicalChartDescriptor],
    *,
    run_kind: str,
    user_overview: Sequence[str] | None = None,
    max_items: int | None = None,
    overview_enabled: bool = True,
) -> list[LogicalChartDescriptor]:
    """Filter logical charts to those matching overview slots."""
    enabled_ids = resolve_overview_viz_ids(
        run_kind=run_kind,
        user_overview=user_overview,
        max_items=max_items,
        overview_enabled=overview_enabled,
    )
    enabled = set(enabled_ids)
    by_viz: dict[str, list[LogicalChartDescriptor]] = {}
    for chart in charts:
        if chart.viz_id in enabled:
            by_viz.setdefault(chart.viz_id, []).append(chart)
    ordered: list[LogicalChartDescriptor] = []
    for viz_id in enabled_ids:
        ordered.extend(by_viz.get(viz_id) or [])
    return ordered


def overview_slot_meta(viz_id: str) -> dict[str, Any]:
    """Registry label/description for an overview viz_id."""
    registry = get_chart_registry()
    cd = registry.get(viz_id)
    if not cd:
        return {"viz_id": viz_id, "label": viz_id, "description": None}
    desc = cd.description.strip() if cd.description and cd.description.strip() else None
    return {"viz_id": viz_id, "label": cd.label, "description": desc}
