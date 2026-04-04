"""Pooled corpus-level entity-sentiment charts (``pooled_single_view``)."""

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


class EntitySentimentPooledGroupChartGenerator:
    """Requires ``entity_sentiment_pooled``; fail-closed if missing or empty."""

    agg_id = "entity_sentiment"

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        p = outcome.get("entity_sentiment_pooled")
        if not isinstance(p, dict):
            return False
        entities = p.get("entities")
        return isinstance(entities, list) and len(entities) > 0

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        p = outcome.get("entity_sentiment_pooled")
        if not isinstance(p, dict):
            return None
        entities = p.get("entities")
        if not isinstance(entities, list) or not entities:
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

        top = entities[:15]
        labels = [f"{e.get('entity', '')} ({e.get('entity_type', '')})" for e in top]
        mentions = [float(e.get("mentions") or 0) for e in top]
        if not any(mentions):
            return None

        svc.save_chart(
            BarCategoricalSpec(
                viz_id="group.entity_sentiment.pooled.top_entities.global",
                module=self.agg_id,
                name="entity_sentiment_pooled_top",
                scope="global",
                chart_intent="bar_categorical",
                title="Group pooled — top entities by mentions (mean sentiment in data)",
                x_label="Entity",
                y_label="Mentions",
                categories=labels,
                values=mentions,
            ),
            chart_type="bar",
        )

        out = chart_artifact_paths(svc)
        return out or None
