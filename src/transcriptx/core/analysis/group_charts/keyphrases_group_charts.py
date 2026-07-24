"""Keyphrases group chart: top-N pooled noun_chunk bar."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.helpers import (
    chart_artifact_paths,
    make_group_output_service,
)
from transcriptx.core.viz.specs import BarCategoricalSpec


class KeyphrasesGroupChartGenerator:
    agg_id = "keyphrases"

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        pooled = outcome.get("keyphrases_pooled")
        if not isinstance(pooled, dict):
            return False
        phrases = pooled.get("phrases")
        return isinstance(phrases, list) and bool(phrases)

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        pooled = outcome.get("keyphrases_pooled")
        if not isinstance(pooled, dict):
            return None
        phrases = pooled.get("phrases") or []
        if not isinstance(phrases, list) or not phrases:
            return None
        top = phrases[:20]
        cats = [str(p.get("phrase") or p.get("canonical_key") or "") for p in top]
        vals = [float(p.get("rank_weight") or 0.0) for p in top]
        cats = [c for c in cats if c]
        if not cats:
            return None
        vals = vals[: len(cats)]
        svc = make_group_output_service(
            ctx, module_name=self.agg_id, agg_id=self.agg_id
        )
        svc.save_chart(
            BarCategoricalSpec(
                viz_id="keyphrases.phrases.global",
                module=self.agg_id,
                name="keyphrases_pooled_noun_chunks",
                scope="global",
                chart_intent="bar_categorical",
                title="Group pooled — keyphrases (noun_chunks)",
                x_label="Phrase",
                y_label="Rank weight",
                categories=cats,
                values=vals,
            ),
            chart_type="bar",
        )
        return chart_artifact_paths(svc) or None
