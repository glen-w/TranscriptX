"""Group charts for transcript_quality — cohort-safe session comparisons."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.helpers import (
    chart_artifact_paths,
    make_group_output_service,
    session_row_label,
)
from transcriptx.core.utils.viz_ids import VIZ_GROUP_TRANSCRIPT_QUALITY_COVERAGE
from transcriptx.core.viz.specs import BarCategoricalSpec


def _primary_comparable_key(
    session_rows: List[Dict[str, Any]], pooled: Dict[str, Any]
) -> str:
    key = str(pooled.get("comparable_key") or "")
    if key:
        return key
    by_key: Dict[str, List[Dict[str, Any]]] = {}
    for row in session_rows:
        by_key.setdefault(str(row.get("comparable_key") or ""), []).append(row)
    if not by_key:
        return ""

    def _rank(k: str) -> tuple[int, int, str]:
        rows = by_key[k]
        scored = sum(int(r.get("scored_word_count") or 0) for r in rows)
        return (len(rows), scored, k)

    return max(by_key.keys(), key=_rank)


class TranscriptQualityGroupChartGenerator:
    """Compare ASR confidence metrics only within one provenance cohort."""

    agg_id = "transcript_quality"

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        session_rows = list(outcome.get("session_rows") or [])
        if not session_rows:
            return False
        pooled = outcome.get("transcript_quality_pooled") or {}
        primary_key = _primary_comparable_key(session_rows, pooled)
        if not primary_key:
            return False
        return any(
            str(r.get("comparable_key") or "") == primary_key for r in session_rows
        )

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        session_rows = list(outcome.get("session_rows") or [])
        pooled = outcome.get("transcript_quality_pooled") or {}
        primary_key = _primary_comparable_key(session_rows, pooled)
        if not primary_key:
            return None

        cohort_rows = [
            r for r in session_rows if str(r.get("comparable_key") or "") == primary_key
        ]
        if not cohort_rows:
            # Never fall back to blending incompatible provenance cohorts.
            return None

        cohort_rows.sort(key=lambda r: r.get("order_index", 0))
        svc = make_group_output_service(
            ctx, module_name=self.agg_id, agg_id=self.agg_id
        )

        incompatible = int(
            pooled.get("incompatible_member_count")
            if pooled.get("incompatible_member_count") is not None
            else max(0, len(session_rows) - len(cohort_rows))
        )
        cohort_note = (
            f"provenance={primary_key}"
            + (f"; excluded incompatible={incompatible}" if incompatible else "")
        )
        prefix = (
            "Group ASR confidence (comparable cohort only; not cross-model quality)"
        )

        for metric, y_label, viz_suffix in (
            ("coverage_ratio", "Score coverage", "coverage_ratio"),
            ("mean_score", "Mean score (scored words)", "mean_score"),
            ("low_score_ratio", "Low-score ratio", "low_score_ratio"),
        ):
            labels: List[str] = []
            vals: List[float] = []
            for row in cohort_rows:
                raw = row.get(metric)
                if not isinstance(raw, (int, float)):
                    continue
                labels.append(session_row_label(row, ctx.transcript_set))
                vals.append(float(raw))
            if not vals:
                continue
            viz_id = (
                VIZ_GROUP_TRANSCRIPT_QUALITY_COVERAGE
                if metric == "coverage_ratio"
                else f"group.transcript_quality.session.{viz_suffix}"
            )
            svc.save_chart(
                BarCategoricalSpec(
                    viz_id=viz_id,
                    module=self.agg_id,
                    name=f"group_session_{viz_suffix}"[:80],
                    scope="global",
                    chart_intent="bar_categorical",
                    title=f"{prefix} — {y_label} ({cohort_note})",
                    x_label="Session",
                    y_label=y_label,
                    categories=labels,
                    values=vals,
                ),
                chart_type="bar",
            )

        out = chart_artifact_paths(svc)
        return out or None
