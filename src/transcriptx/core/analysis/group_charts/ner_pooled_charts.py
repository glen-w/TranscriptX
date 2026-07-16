"""Pooled corpus-level NER charts (``pooled_single_view``)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.helpers import (
    make_group_output_service,
    chart_artifact_paths,
)
from transcriptx.core.viz.specs import BarCategoricalSpec


class NerPooledGroupChartGenerator:
    """Requires allowlisted ``ner_pooled`` on chart outcome; fail-closed otherwise."""

    agg_id = "ner"

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        p = outcome.get("ner_pooled")
        if not isinstance(p, dict):
            return False
        counts = p.get("entity_type_counts")
        if not isinstance(counts, dict) or not counts:
            return False
        return sum(int(v) for v in counts.values() if isinstance(v, (int, float))) > 0

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        p = outcome.get("ner_pooled")
        if not isinstance(p, dict):
            return None
        counts = p.get("entity_type_counts")
        if not isinstance(counts, dict) or not counts:
            return None

        svc = make_group_output_service(
            ctx, module_name=self.agg_id, agg_id=self.agg_id
        )

        cats = sorted(counts.keys(), key=lambda k: (-int(counts[k] or 0), k))
        vals = [float(counts[k]) for k in cats]
        svc.save_chart(
            BarCategoricalSpec(
                viz_id="group.ner.pooled.entity_types.global",
                module=self.agg_id,
                name="ner_pooled_entity_types",
                scope="global",
                chart_intent="bar_categorical",
                title="Group pooled — entity type counts (full corpus)",
                x_label="Entity type",
                y_label="Mentions",
                categories=list(cats),
                values=vals,
            ),
            chart_type="entity_types",
        )

        top = p.get("top_entities")
        if isinstance(top, list) and top:
            top_n = top[:15]
            labels = [
                f"{e.get('entity', '')} ({e.get('entity_type', '')})" for e in top_n
            ]
            mentions = [float(e.get("mentions") or 0) for e in top_n]
            if any(mentions):
                svc.save_chart(
                    BarCategoricalSpec(
                        viz_id="group.ner.pooled.top_entities.global",
                        module=self.agg_id,
                        name="ner_pooled_top_entities",
                        scope="global",
                        chart_intent="bar_categorical",
                        title="Group pooled — top entities by mention count",
                        x_label="Entity",
                        y_label="Mentions",
                        categories=labels,
                        values=mentions,
                    ),
                    chart_type="bar",
                )

        out = chart_artifact_paths(svc)
        return out or None
