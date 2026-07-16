"""Group aggregate charts for highlights and moments (content_rows)."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.helpers import (
    make_group_output_service,
    chart_artifact_paths,
    session_row_label,
)
from transcriptx.core.viz.specs import BarCategoricalSpec


def _session_rows_by_order(
    session_rows: List[Dict[str, Any]],
) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for row in session_rows:
        oi = row.get("order_index")
        if isinstance(oi, int):
            out[oi] = row
    return out


def _numeric_scores(rows: List[Dict[str, Any]]) -> List[float]:
    vals: List[float] = []
    for row in rows:
        s = row.get("score")
        if isinstance(s, (int, float)) and not isinstance(s, bool):
            vals.append(float(s))
    return vals


class HighlightsGroupChartGenerator:
    agg_id = "highlights"

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        rows = outcome.get("content_rows") or []
        if not rows:
            return False
        return bool(_numeric_scores(rows)) or len(rows) >= 1

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        content_rows: List[Dict[str, Any]] = list(outcome.get("content_rows") or [])
        if not content_rows:
            return None
        session_rows = list(outcome.get("session_rows") or [])
        by_order = _session_rows_by_order(session_rows)

        svc = make_group_output_service(
            ctx, module_name=self.agg_id, agg_id=self.agg_id
        )
        prefix = "Group aggregate (highlights summary by session; not a within-session timeline)"

        counts: Dict[int, int] = defaultdict(int)
        for row in content_rows:
            oi = row.get("order_index")
            if isinstance(oi, int):
                counts[oi] += 1
        order_keys = sorted(counts.keys())
        if order_keys:
            labels = [
                session_row_label(
                    by_order.get(oi, {"order_index": oi}), ctx.transcript_set
                )
                for oi in order_keys
            ]
            vals = [float(counts[oi]) for oi in order_keys]
            svc.save_chart(
                BarCategoricalSpec(
                    viz_id="group.highlights.session_counts",
                    module=self.agg_id,
                    name="highlights_per_session",
                    scope="global",
                    chart_intent="bar_categorical",
                    title=f"{prefix} — highlight count per session",
                    x_label="Session",
                    y_label="Count",
                    categories=labels,
                    values=vals,
                ),
                chart_type="bar",
            )

        scores = _numeric_scores(content_rows)
        if scores:
            sum_by: Dict[int, float] = defaultdict(float)
            n_by: Dict[int, int] = defaultdict(int)
            for row in content_rows:
                s = row.get("score")
                if not isinstance(s, (int, float)) or isinstance(s, bool):
                    continue
                oi = row.get("order_index")
                if not isinstance(oi, int):
                    continue
                sum_by[oi] += float(s)
                n_by[oi] += 1
            okeys = sorted(k for k in sum_by if n_by[k] > 0)
            if okeys:
                labels = [
                    session_row_label(
                        by_order.get(oi, {"order_index": oi}), ctx.transcript_set
                    )
                    for oi in okeys
                ]
                means = [sum_by[oi] / n_by[oi] for oi in okeys]
                svc.save_chart(
                    BarCategoricalSpec(
                        viz_id="group.highlights.session_mean_score",
                        module=self.agg_id,
                        name="highlights_mean_score",
                        scope="global",
                        chart_intent="bar_categorical",
                        title=f"{prefix} — mean highlight score per session",
                        x_label="Session",
                        y_label="Mean score",
                        categories=labels,
                        values=means,
                    ),
                    chart_type="bar",
                )

        out = chart_artifact_paths(svc)
        return out or None


class MomentsGroupChartGenerator:
    agg_id = "moments"

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        rows = outcome.get("content_rows") or []
        if not rows:
            return False
        return bool(_numeric_scores(rows)) or len(rows) >= 1

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        content_rows = list(outcome.get("content_rows") or [])
        if not content_rows:
            return None
        session_rows = list(outcome.get("session_rows") or [])
        by_order = _session_rows_by_order(session_rows)

        svc = make_group_output_service(
            ctx, module_name=self.agg_id, agg_id=self.agg_id
        )
        prefix = "Group aggregate (moments summary by session; not a within-session timeline)"

        counts: Dict[int, int] = defaultdict(int)
        for row in content_rows:
            oi = row.get("order_index")
            if isinstance(oi, int):
                counts[oi] += 1
        order_keys = sorted(counts.keys())
        if order_keys:
            labels = [
                session_row_label(
                    by_order.get(oi, {"order_index": oi}), ctx.transcript_set
                )
                for oi in order_keys
            ]
            vals = [float(counts[oi]) for oi in order_keys]
            svc.save_chart(
                BarCategoricalSpec(
                    viz_id="group.moments.session_counts",
                    module=self.agg_id,
                    name="moments_per_session",
                    scope="global",
                    chart_intent="bar_categorical",
                    title=f"{prefix} — moment count per session",
                    x_label="Session",
                    y_label="Count",
                    categories=labels,
                    values=vals,
                ),
                chart_type="bar",
            )

        scores = _numeric_scores(content_rows)
        if scores:
            sum_by = defaultdict(float)
            n_by = defaultdict(int)
            for row in content_rows:
                s = row.get("score")
                if not isinstance(s, (int, float)) or isinstance(s, bool):
                    continue
                oi = row.get("order_index")
                if not isinstance(oi, int):
                    continue
                sum_by[oi] += float(s)
                n_by[oi] += 1
            okeys = sorted(k for k in sum_by if n_by[k] > 0)
            if okeys:
                labels = [
                    session_row_label(
                        by_order.get(oi, {"order_index": oi}), ctx.transcript_set
                    )
                    for oi in okeys
                ]
                means = [sum_by[oi] / n_by[oi] for oi in okeys]
                svc.save_chart(
                    BarCategoricalSpec(
                        viz_id="group.moments.session_mean_score",
                        module=self.agg_id,
                        name="moments_mean_score",
                        scope="global",
                        chart_intent="bar_categorical",
                        title=f"{prefix} — mean moment score per session",
                        x_label="Session",
                        y_label="Mean score",
                        categories=labels,
                        values=means,
                    ),
                    chart_type="bar",
                )

        out = chart_artifact_paths(svc)
        return out or None
