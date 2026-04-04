"""Generic session-level bar charts from numeric columns in aggregation rows."""

from __future__ import annotations

from pathlib import Path
from typing import AbstractSet, Any, Dict, List, Optional

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.helpers import (
    SESSION_META_KEYS,
    chart_artifact_paths,
    merge_numeric_keys_from_session_rows,
    session_row_label,
)
from transcriptx.core.analysis.group_charts.output_service import (
    GroupChartOutputService,
)
from transcriptx.core.analysis.group_charts.virtual_path import (
    build_group_virtual_transcript_path,
)
from transcriptx.core.viz.specs import BarCategoricalSpec


class GenericNumericGroupChartGenerator:
    """
    One bar chart per numeric session column (capped), for aggregations that
    expose flat numeric session_rows.
    """

    def __init__(
        self,
        agg_id: str,
        *,
        flatten_nested: bool = False,
        max_charts: int = 10,
        allowed_numeric_keys: Optional[AbstractSet[str]] = None,
    ) -> None:
        self.agg_id = agg_id
        self.flatten_nested = flatten_nested
        self.max_charts = max_charts
        self.allowed_numeric_keys = allowed_numeric_keys

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        session_rows = outcome.get("session_rows") or []
        if len(session_rows) < 1:
            return False
        keys = merge_numeric_keys_from_session_rows(
            session_rows,
            exclude=SESSION_META_KEYS,
            flatten_dict_one_level=self.flatten_nested,
        )
        if self.allowed_numeric_keys is not None:
            keys = [k for k in keys if k in self.allowed_numeric_keys]
        return len(keys) > 0

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        session_rows = list(outcome.get("session_rows") or [])
        session_rows.sort(key=lambda r: r.get("order_index", 0))
        keys = merge_numeric_keys_from_session_rows(
            session_rows,
            exclude=SESSION_META_KEYS,
            flatten_dict_one_level=self.flatten_nested,
        )
        if not keys:
            return None
        if self.allowed_numeric_keys is not None:
            keys = [k for k in keys if k in self.allowed_numeric_keys]
        if not keys:
            return None
        keys = keys[: self.max_charts]

        virtual = build_group_virtual_transcript_path(ctx.group_run_root, self.agg_id)
        svc = GroupChartOutputService(
            virtual_transcript_path=virtual,
            module_name=self.agg_id,
            output_dir=str(ctx.group_run_root.resolve()),
            run_id=ctx.group_run_id,
            agg_id=self.agg_id,
            group_uuid=ctx.group_uuid,
        )
        labels = [session_row_label(r, ctx.transcript_set) for r in session_rows]
        prefix = f"Group aggregate ({self.agg_id} summary by session)"

        for key in keys:
            vals: List[float] = []
            for row in session_rows:
                parts = key.split(".", 1)
                if len(parts) == 2 and isinstance(row.get(parts[0]), dict):
                    inner = row[parts[0]]
                    vals.append(float(inner.get(parts[1]) or 0))
                else:
                    vals.append(float(row.get(key) or 0))
            if not any(vals):
                continue
            safe_name = key.replace(".", "_")
            svc.save_chart(
                BarCategoricalSpec(
                    viz_id=f"group.{self.agg_id}.session.{safe_name}",
                    module=self.agg_id,
                    name=f"group_session_{safe_name}"[:80],
                    scope="global",
                    chart_intent="bar_categorical",
                    title=f"{prefix} — {key}",
                    x_label="Session",
                    y_label=key,
                    categories=labels,
                    values=vals,
                ),
                chart_type="bar",
            )

        out = chart_artifact_paths(svc)
        return out or None
