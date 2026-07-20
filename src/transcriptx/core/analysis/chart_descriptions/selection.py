"""chart_set selection over logical chart inventories."""

from __future__ import annotations

from typing import Literal, Sequence

from transcriptx.core.analysis.chart_descriptions.inventory import LogicalChartDescriptor
from transcriptx.core.analysis.chart_descriptions.overview import select_overview_descriptors

ChartSet = Literal["all", "transcript_group", "overview_only"]


def select_charts_for_set(
    charts: Sequence[LogicalChartDescriptor],
    *,
    chart_set: ChartSet,
    run_kind: str,
    user_overview: Sequence[str] | None = None,
    max_items: int | None = None,
) -> list[LogicalChartDescriptor]:
    """Apply chart_set filter, then deterministic sort by chart_key."""
    if chart_set == "all":
        selected = list(charts)
    elif chart_set == "transcript_group":
        if run_kind == "group":
            selected = [
                c for c in charts if c.provenance_kind == "group_aggregate"
            ]
        else:
            selected = [
                c for c in charts if c.provenance_kind == "transcript"
            ]
    elif chart_set == "overview_only":
        selected = select_overview_descriptors(
            charts,
            run_kind=run_kind,
            user_overview=user_overview,
            max_items=max_items,
        )
    else:
        raise ValueError(f"Unknown chart_set: {chart_set}")

    # Deduplicate by chart_key (paired static/dynamic already one unit).
    seen: set[str] = set()
    unique: list[LogicalChartDescriptor] = []
    for chart in selected:
        if chart.chart_key in seen:
            continue
        seen.add(chart.chart_key)
        unique.append(chart)
    unique.sort(key=lambda c: c.chart_key)
    return unique
