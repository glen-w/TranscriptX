"""Composite group charts for semantic_similarity (session bars + motif prevalence)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.generic_numeric import (
    GenericNumericGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.helpers import (
    chart_artifact_paths,
    make_group_output_service,
    session_row_label,
)
from transcriptx.core.viz.specs import BarCategoricalSpec

VIZ_MOTIF_PREVALENCE = "group.semantic_similarity.motif_prevalence.global"

_REPETITION_KEYS = frozenset({"total_repetitions", "unique_patterns"})
_NULL_SAFE_KEYS = (
    ("motif_count", "Motif count", "group.semantic_similarity.session.motif_count"),
    (
        "recurring_motif_count",
        "Recurring motif count",
        "group.semantic_similarity.session.recurring_motif_count",
    ),
    ("drift_score", "Drift score", "group.semantic_similarity.session.drift_score"),
)


class SemanticSimilarityGroupChartGenerator:
    """Delegates repetition session bars to generic; null-safe motif scalars + prevalence."""

    agg_id = "semantic_similarity"

    def __init__(self) -> None:
        self._session_bars = GenericNumericGroupChartGenerator(
            self.agg_id,
            flatten_nested=True,
            max_charts=10,
            allowed_numeric_keys=_REPETITION_KEYS,
        )

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        if self._session_bars.can_generate(outcome):
            return True
        if self._has_null_safe_bars(outcome):
            return True
        return self._can_motif_prevalence(outcome)

    def _has_null_safe_bars(self, outcome: Dict[str, Any]) -> bool:
        rows = outcome.get("session_rows") or []
        for key, _, _ in _NULL_SAFE_KEYS:
            if any(isinstance(r.get(key), (int, float)) for r in rows):
                return True
        return False

    def _can_motif_prevalence(self, outcome: Dict[str, Any]) -> bool:
        pooled = outcome.get("semantic_similarity_pooled") or {}
        recurring = list(pooled.get("recurring_motif_ids") or [])
        orders = list(pooled.get("order_indexes") or [])
        comparable = [
            r
            for r in (outcome.get("session_rows") or [])
            if r.get("included_in_comparison")
        ]
        return len(comparable) >= 2 and len(recurring) >= 1 and len(orders) >= 2

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        paths: List[Path] = []
        bar_paths = self._session_bars.generate(ctx, outcome)
        if bar_paths:
            paths.extend(bar_paths)

        null_safe = self._generate_null_safe_bars(ctx, outcome)
        if null_safe:
            paths.extend(null_safe)

        if self._can_motif_prevalence(outcome):
            motif_paths = self._generate_motif_prevalence(ctx, outcome)
            if motif_paths:
                paths.extend(motif_paths)

        return paths or None

    def _generate_null_safe_bars(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        session_rows = sorted(
            list(outcome.get("session_rows") or []),
            key=lambda r: r.get("order_index", 0),
        )
        if not session_rows:
            return None
        svc = make_group_output_service(
            ctx, module_name=self.agg_id, agg_id=self.agg_id
        )
        emitted = False
        for key, y_label, viz_id in _NULL_SAFE_KEYS:
            labels: List[str] = []
            vals: List[float] = []
            for row in session_rows:
                raw = row.get(key)
                if not isinstance(raw, (int, float)):
                    continue
                labels.append(session_row_label(row, ctx.transcript_set))
                vals.append(float(raw))
            if not vals:
                continue
            emitted = True
            svc.save_chart(
                BarCategoricalSpec(
                    viz_id=viz_id,
                    module=self.agg_id,
                    name=f"group_session_{key}"[:80],
                    scope="global",
                    chart_intent="bar_categorical",
                    title=f"Group semantic similarity — {y_label}",
                    x_label="Session",
                    y_label=y_label,
                    categories=labels,
                    values=vals,
                ),
                chart_type="bar",
            )
        out = chart_artifact_paths(svc) if emitted else []
        return out or None

    def _generate_motif_prevalence(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        pooled = outcome.get("semantic_similarity_pooled") or {}
        orders = [int(o) for o in (pooled.get("order_indexes") or [])]
        recurring_ids = list(pooled.get("recurring_motif_ids") or [])
        motif_ids = list(pooled.get("motif_ids") or [])
        strength = list(pooled.get("strength_matrix") or [])
        if not orders or not recurring_ids or not strength:
            return None

        id_to_row = {
            mid: strength[i] for i, mid in enumerate(motif_ids) if i < len(strength)
        }
        session_rows = {
            int(r.get("order_index", 0)): r for r in (outcome.get("session_rows") or [])
        }
        categories = []
        for o in orders:
            row = session_rows.get(o) or {"order_index": o}
            categories.append(session_row_label(row, ctx.transcript_set))

        svc = make_group_output_service(
            ctx, module_name=self.agg_id, agg_id=self.agg_id
        )
        totals: List[float] = []
        for col, _o in enumerate(orders):
            total = 0.0
            for mid in recurring_ids:
                row = id_to_row.get(mid) or []
                if col < len(row):
                    total += float(row[col] or 0.0)
            totals.append(total)

        if any(v > 0 for v in totals):
            svc.save_chart(
                BarCategoricalSpec(
                    viz_id=VIZ_MOTIF_PREVALENCE,
                    module=self.agg_id,
                    name="motif_prevalence",
                    scope="global",
                    chart_intent="bar_categorical",
                    title=(
                        "Group semantic motifs — recurring motif strength "
                        "(cluster size; order_index)"
                    ),
                    x_label="Session (order_index)",
                    y_label="Recurring motif cluster size (sum)",
                    categories=categories,
                    values=totals,
                ),
                chart_type="bar",
            )

        for mid in recurring_ids:
            row = id_to_row.get(mid)
            if not row:
                continue
            vals = [
                float(row[i] or 0.0) if i < len(row) else 0.0
                for i in range(len(orders))
            ]
            if not any(vals):
                continue
            safe = mid[:12]
            svc.save_chart(
                BarCategoricalSpec(
                    viz_id=f"group.semantic_similarity.motif.{safe}.global",
                    module=self.agg_id,
                    name=f"motif_{safe}"[:80],
                    scope="global",
                    chart_intent="bar_categorical",
                    title=f"Motif {safe} — cluster size by session",
                    x_label="Session (order_index)",
                    y_label="Cluster size",
                    categories=categories,
                    values=vals,
                ),
                chart_type="bar",
            )

        out = chart_artifact_paths(svc)
        return out or None
