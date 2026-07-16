"""Group charts for topic_modeling aggregation (``pooled_single_view`` only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.helpers import (
    make_group_output_service,
    chart_artifact_paths,
)
from transcriptx.core.viz.specs import BarCategoricalSpec


class TopicModelingGroupChartGenerator:
    """Pooled LDA topic prevalence for the combined corpus."""

    agg_id = "topic_modeling"

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        p = outcome.get("topic_modeling_pooled")
        if not isinstance(p, dict):
            return False
        topics = p.get("topics")
        return isinstance(topics, list) and len(topics) > 0

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        p = outcome.get("topic_modeling_pooled")
        if not isinstance(p, dict):
            return None
        topics = p.get("topics")
        if not isinstance(topics, list) or not topics:
            return None

        svc = make_group_output_service(
            ctx, module_name=self.agg_id, agg_id=self.agg_id
        )

        labels: List[str] = []
        vals: List[float] = []
        for row in topics:
            tid = row.get("topic_id")
            share = float(row.get("topic_share") or 0)
            terms = str(row.get("top_terms") or "")[:40]
            labels.append(f"Topic {tid}: {terms}".strip())
            vals.append(share)

        if not any(vals):
            return None

        svc.save_chart(
            BarCategoricalSpec(
                viz_id="group.topic_modeling.pooled.topic_share.global",
                module=self.agg_id,
                name="topic_modeling_pooled_share",
                scope="global",
                chart_intent="bar_categorical",
                title="Group pooled — topic prevalence (group LDA over merged segments)",
                x_label="Topic",
                y_label="Mean document-topic share",
                categories=labels,
                values=vals,
            ),
            chart_type="bar",
        )

        out = chart_artifact_paths(svc)
        return out or None
