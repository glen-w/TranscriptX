"""Epistemic markers: session bars plus pooled category counts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.generic_field_allowlists import (
    allowed_numeric_keys_for_generic_agg,
)
from transcriptx.core.analysis.group_charts.generic_numeric import (
    GenericNumericGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.helpers import (
    chart_artifact_paths,
    make_group_output_service,
)
from transcriptx.core.viz.specs import BarCategoricalSpec


class EpistemicMarkersGroupChartGenerator:
    agg_id = "epistemic_markers"

    def __init__(self) -> None:
        allow = allowed_numeric_keys_for_generic_agg("epistemic_markers")
        self._session = GenericNumericGroupChartGenerator(
            "epistemic_markers",
            flatten_nested=True,
            max_charts=10,
            allowed_numeric_keys=allow,
        )

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        if self._session.can_generate(outcome):
            return True
        p = outcome.get("epistemic_markers_pooled")
        if not isinstance(p, dict):
            return False
        by_cat = p.get("by_category")
        return isinstance(by_cat, dict) and bool(by_cat)

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        paths: List[Path] = []
        sub = self._session.generate(ctx, outcome)
        if sub is not None:
            paths.extend(sub)
        p = outcome.get("epistemic_markers_pooled")
        if isinstance(p, dict):
            by_cat = p.get("by_category")
            if isinstance(by_cat, dict) and by_cat:
                svc = make_group_output_service(
                    ctx, module_name=self.agg_id, agg_id=self.agg_id
                )
                cats = sorted(by_cat.keys(), key=lambda k: (-int(by_cat[k] or 0), k))
                vals = [float(by_cat[k]) for k in cats]
                svc.save_chart(
                    BarCategoricalSpec(
                        viz_id="group.epistemic_markers.pooled.by_category.global",
                        module=self.agg_id,
                        name="epistemic_markers_pooled_by_category",
                        scope="global",
                        chart_intent="bar_categorical",
                        title="Group pooled — epistemic marker counts",
                        x_label="Category",
                        y_label="Count",
                        categories=list(cats),
                        values=vals,
                    ),
                    chart_type="bar",
                )
                paths.extend(chart_artifact_paths(svc))
        return paths or None
