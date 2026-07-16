"""
Group aggregate charts for pauses.

Two explicit families (see ``GROUP_AGGREGATE_CHART_FAMILIES`` in ``registry.py``):

1. **session_summary_bars** — numeric fields from group ``session_rows`` (same bar pattern as generic numeric).
2. **temporal_overlay** — optional cross-session long-pause lines from member ``pauses.events.json``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.context_guards import (
    should_emit_temporal_overlay_charts,
)
from transcriptx.core.analysis.group_charts.overlay_series import (
    cap_per_transcript_results_for_overlay,
)
from transcriptx.core.analysis.group_charts.helpers import (
    make_group_output_service,
    SESSION_META_KEYS,
    chart_artifact_paths,
    member_session_label,
    merge_numeric_keys_from_session_rows,
    session_row_label,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.io.events_io import load_events_json
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.viz.specs import BarCategoricalSpec, LineTimeSeriesSpec

_PREFIX = "Group aggregate (pauses summary, not cross-session wall-clock)"
_TIMELINE_KINDS = frozenset({"long_pause", "post_question_silence"})


def _events_path(result: PerTranscriptResult) -> Path:
    return Path(result.output_dir) / "pauses" / "data" / "global" / "pauses.events.json"


def generate_group_pauses_temporal_overlay(
    output_service: GroupChartOutputService,
    per_transcript_results: Sequence[PerTranscriptResult],
    transcript_set: TranscriptSet,
    *,
    title_prefix: str | None = None,
) -> None:
    """Cross-session long-pause markers; see ``docs/groups/group_charts_pauses_temporal_contract.md``."""

    def _tp(title: str) -> str:
        if not title_prefix:
            return title
        return f"{title_prefix} — {title}"

    ordered = cap_per_transcript_results_for_overlay(per_transcript_results)

    temporal_series: List[Dict[str, Any]] = []
    for result in ordered:
        path = _events_path(result)
        if not path.is_file():
            continue
        events = load_events_json(path)
        ev_for_plot = [e for e in events if getattr(e, "kind", None) in _TIMELINE_KINDS]
        if not ev_for_plot:
            continue
        raw_starts = [float(e.time_start) for e in ev_for_plot]
        t0 = min(raw_starts) if raw_starts else 0.0
        sess_label = member_session_label(result, transcript_set)
        times: List[float] = []
        y_vals: List[float] = []
        for e in ev_for_plot:
            ts = float(e.time_start)
            times.append((ts - t0) / 60.0)
            y_vals.append(float(e.time_end - e.time_start))
        if y_vals:
            temporal_series.append({"name": sess_label, "x": times, "y": y_vals})

    if temporal_series:
        output_service.save_chart(
            LineTimeSeriesSpec(
                viz_id="group.pauses.temporal_overlay.global",
                module="pauses",
                name="temporal_overlay",
                scope="global",
                chart_intent="line_timeseries",
                title=_tp(
                    "Long pauses — cross-session overlay; session-relative minutes"
                ),
                x_label="Session-relative minutes from first plotted pause",
                y_label="Gap (seconds)",
                markers=True,
                series=temporal_series,
            ),
            chart_type="temporal",
        )


class PausesGroupChartGenerator:
    agg_id = "pauses"

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        session_rows = outcome.get("session_rows") or []
        if len(session_rows) < 1:
            return False
        keys = merge_numeric_keys_from_session_rows(
            session_rows,
            exclude=SESSION_META_KEYS,
            flatten_dict_one_level=True,
        )
        return len(keys) > 0

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        session_rows = list(outcome.get("session_rows") or [])
        session_rows.sort(key=lambda r: r.get("order_index", 0))
        keys = merge_numeric_keys_from_session_rows(
            session_rows,
            exclude=SESSION_META_KEYS,
            flatten_dict_one_level=True,
        )
        if not keys:
            return None
        keys = keys[:10]

        svc = make_group_output_service(
            ctx, module_name=self.agg_id, agg_id=self.agg_id
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

        if (
            should_emit_temporal_overlay_charts(self.agg_id, ctx.per_transcript_results)
            and ctx.per_transcript_results
        ):
            generate_group_pauses_temporal_overlay(
                svc,
                ctx.per_transcript_results,
                ctx.transcript_set,
                title_prefix=_PREFIX,
            )

        out = chart_artifact_paths(svc)
        return out or None
