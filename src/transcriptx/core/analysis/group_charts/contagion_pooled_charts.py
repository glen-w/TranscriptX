"""Contagion: pooled directed edges from ``contagion_pooled`` (sparse v1 chart)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.helpers import chart_artifact_paths
from transcriptx.core.analysis.group_charts.output_service import (
    GroupChartOutputService,
)
from transcriptx.core.analysis.group_charts.virtual_path import (
    build_group_virtual_transcript_path,
)
from transcriptx.core.viz.specs import BarCategoricalSpec


def _parse_edges(outcome: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    p = outcome.get("contagion_pooled")
    if not isinstance(p, dict):
        return None
    if p.get("schema_version") != 1:
        return None
    edges = p.get("edges")
    if not isinstance(edges, list) or not edges:
        return None
    cleaned: List[Dict[str, Any]] = []
    for e in edges:
        if not isinstance(e, dict):
            continue
        total = e.get("total")
        if not isinstance(total, int):
            try:
                total = int(total or 0)
            except (TypeError, ValueError):
                total = 0
        if total <= 0:
            continue
        fd = e.get("from_display")
        td = e.get("to_display")
        if not isinstance(fd, str) or not isinstance(td, str):
            continue
        cleaned.append(e)
    return cleaned or None


class ContagionPooledGroupChartGenerator:
    """Top directed edges from ``contagion_pooled``; fail-closed if missing or empty."""

    agg_id = "contagion"

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        edges = _parse_edges(outcome)
        return bool(edges)

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        edges = _parse_edges(outcome)
        if not edges:
            return None

        limit = 15
        top = edges[:limit]
        categories = [f"{e['from_display']} → {e['to_display']}" for e in top]
        values = [float(e.get("total") or 0) for e in top]
        if not any(values):
            return None

        virtual = build_group_virtual_transcript_path(ctx.group_run_root, self.agg_id)
        svc = GroupChartOutputService(
            virtual_transcript_path=virtual,
            module_name=self.agg_id,
            output_dir=str(ctx.group_run_root.resolve()),
            run_id=ctx.group_run_id,
            agg_id=self.agg_id,
            group_uuid=ctx.group_uuid,
        )
        svc.save_chart(
            BarCategoricalSpec(
                viz_id="group.contagion.pooled.top_directed_edges.global",
                module=self.agg_id,
                name="contagion_pooled_top_edges",
                scope="global",
                chart_intent="bar_categorical",
                title="Group pooled — top directed contagion edges (observed counts)",
                x_label="From → to",
                y_label="Total events",
                categories=categories,
                values=values,
            ),
            chart_type="bar",
        )
        out = chart_artifact_paths(svc)
        return out or None
