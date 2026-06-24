"""Charts page block implementations (gallery sections extracted for reuse)."""

from __future__ import annotations

from typing import Dict, List

import streamlit as st

from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.placement import BlockPlacement
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.module_ui_groups import order_strings_like_modules


def render_chart_gallery_modules(
    run_root,
    charts: List[Artifact],
    *,
    sections_expanded: bool,
    render_family_section,
) -> None:
    """Render per-module chart expanders (gallery portion of Charts page)."""
    module_groups: Dict[str, List[Artifact]] = {}
    for chart in charts:
        module = chart.module or "Other"
        module_groups.setdefault(module, []).append(chart)

    for module_name in order_strings_like_modules(list(module_groups.keys())):
        module_charts = module_groups[module_name]
        with st.expander(
            f"📊 {module_name} ({len(module_charts)} chart"
            f"{'s' if len(module_charts) != 1 else ''})",
            expanded=sections_expanded,
        ):
            from transcriptx.web.page_modules.charts import (
                group_charts_into_families,
            )

            families = group_charts_into_families(module_charts)
            for fi, family in enumerate(families):
                render_family_section(
                    run_root,
                    family,
                    f"chart_{module_name}_{family.key}",
                    sections_expanded=sections_expanded,
                    show_family_expander=True,
                )
                if fi < len(families) - 1:
                    st.divider()


def render_chart_gallery(ctx: BlockContext, _placement: BlockPlacement) -> None:
    st.caption(
        "Chart gallery is composed on the Charts page with active filters. "
        "Use Dashboard Builder preview on a future charts layout profile."
    )


def render_chart_overview_slots(ctx: BlockContext, _placement: BlockPlacement) -> None:
    st.caption(
        "Overview slots render on the Charts page when **Show Overview** is enabled."
    )
