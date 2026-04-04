"""Tics: session numeric bars (curated) plus pooled corpus tic totals."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.helpers import chart_artifact_paths
from transcriptx.core.analysis.group_charts.generic_field_allowlists import (
    allowed_numeric_keys_for_generic_agg,
)
from transcriptx.core.analysis.group_charts.generic_numeric import (
    GenericNumericGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.output_service import (
    GroupChartOutputService,
)
from transcriptx.core.analysis.group_charts.virtual_path import (
    build_group_virtual_transcript_path,
)
from transcriptx.core.viz.specs import BarCategoricalSpec


class TicsGroupChartGenerator:
    """Session bars via curated generic numeric path; pooled chart from ``tics_pooled``."""

    agg_id = "tics"

    def __init__(self) -> None:
        allow = allowed_numeric_keys_for_generic_agg("tics")
        self._session = GenericNumericGroupChartGenerator(
            "tics",
            flatten_nested=True,
            max_charts=10,
            allowed_numeric_keys=allow,
        )

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        if self._session.can_generate(outcome):
            return True
        p = outcome.get("tics_pooled")
        if not isinstance(p, dict):
            return False
        by_tic = p.get("by_tic")
        total = p.get("total_tics")
        if isinstance(by_tic, dict) and by_tic:
            return True
        return isinstance(total, (int, float)) and int(total) > 0

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        paths: List[Path] = []
        sub = self._session.generate(ctx, outcome)
        if sub is not None:
            paths.extend(sub)

        p = outcome.get("tics_pooled")
        if isinstance(p, dict):
            by_tic = p.get("by_tic")
            if isinstance(by_tic, dict) and by_tic:
                virtual = build_group_virtual_transcript_path(
                    ctx.group_run_root, self.agg_id
                )
                svc = GroupChartOutputService(
                    virtual_transcript_path=virtual,
                    module_name=self.agg_id,
                    output_dir=str(ctx.group_run_root.resolve()),
                    run_id=ctx.group_run_id,
                    agg_id=self.agg_id,
                    group_uuid=ctx.group_uuid,
                )
                cats = sorted(by_tic.keys(), key=lambda k: (-int(by_tic[k] or 0), k))
                vals = [float(by_tic[k]) for k in cats]
                svc.save_chart(
                    BarCategoricalSpec(
                        viz_id="group.tics.pooled.by_tic.global",
                        module=self.agg_id,
                        name="tics_pooled_by_tic",
                        scope="global",
                        chart_intent="bar_categorical",
                        title="Group pooled — verbal tic / filler counts (full corpus)",
                        x_label="Tic / category",
                        y_label="Count",
                        categories=list(cats),
                        values=vals,
                    ),
                    chart_type="bar",
                )
                paths.extend(chart_artifact_paths(svc))

        return paths or None
