"""Group aggregate charts for stats module (session / speaker summary bars)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.context_guards import (
    should_emit_cross_session_speaker_charts,
)
from transcriptx.core.analysis.group_charts.helpers import (
    make_group_output_service,
    chart_artifact_paths,
    filter_chartable_speaker_rows,
    session_row_label,
)
from transcriptx.core.analysis.group_charts.speaker_cross_session import (
    collect_stats_cross_session_speaker_segment_count_series,
    collect_stats_cross_session_speaker_series,
)
from transcriptx.core.viz.specs import BarCategoricalSpec

_SESSION_METRICS = (
    "speaker_count",
    "total_words",
    "total_segments",
    "total_duration",
)


class StatsGroupChartGenerator:
    agg_id = "stats"

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        session_rows = outcome.get("session_rows") or []
        if len(session_rows) < 1:
            return False
        for row in session_rows:
            for m in _SESSION_METRICS:
                v = row.get(m)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    return True
        spk = filter_chartable_speaker_rows(outcome.get("speaker_rows") or [])
        return len(spk) > 0

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        session_rows = list(outcome.get("session_rows") or [])
        speaker_rows = outcome.get("speaker_rows") or []
        session_rows.sort(key=lambda r: r.get("order_index", 0))

        svc = make_group_output_service(
            ctx, module_name=self.agg_id, agg_id=self.agg_id
        )
        prefix = "Group aggregate (per-session summary)"
        labels = [session_row_label(r, ctx.transcript_set) for r in session_rows]

        for metric in _SESSION_METRICS:
            vals = [float(r.get(metric) or 0) for r in session_rows]
            if not any(vals):
                continue
            svc.save_chart(
                BarCategoricalSpec(
                    viz_id=f"group.stats.session.{metric}",
                    module=self.agg_id,
                    name=f"group_session_{metric}",
                    scope="global",
                    chart_intent="bar_categorical",
                    title=f"{prefix} — {metric.replace('_', ' ').title()} by Session",
                    x_label="Session",
                    y_label=metric.replace("_", " ").title(),
                    categories=labels,
                    values=vals,
                ),
                chart_type="bar",
            )

        eligible = filter_chartable_speaker_rows(speaker_rows)
        if eligible:
            names = [
                str(r.get("display_name") or r.get("canonical_speaker_id"))
                for r in eligible
            ]
            for metric in ("total_word_count", "total_segment_count", "total_duration"):
                values = [float(r.get(metric) or 0) for r in eligible]
                if not any(values):
                    continue
                svc.save_chart(
                    BarCategoricalSpec(
                        viz_id=f"group.stats.speakers.{metric}",
                        module=self.agg_id,
                        name=f"group_speakers_{metric}",
                        scope="global",
                        chart_intent="bar_categorical",
                        title=f"{prefix} — {metric.replace('_', ' ').title()} by Speaker (group roll-up)",
                        x_label="Speaker",
                        y_label=metric.replace("_", " ").title(),
                        categories=names,
                        values=values,
                    ),
                    chart_type="bar",
                )

        if (
            should_emit_cross_session_speaker_charts(
                self.agg_id, ctx.canonical_speaker_map
            )
            and ctx.per_transcript_results
        ):
            cmap = ctx.canonical_speaker_map
            assert cmap is not None
            ptr = ctx.per_transcript_results
            cross = collect_stats_cross_session_speaker_series(
                ptr,
                ctx.transcript_set,
                cmap,
            )
            for series in cross:
                sid = int(series.canonical_speaker_id)
                svc.save_chart(
                    BarCategoricalSpec(
                        viz_id=f"group.stats.cross_session_speaker.speaker_{sid}",
                        module=self.agg_id,
                        name=f"stats_cross_session_speaker_{sid}"[:80],
                        scope="speaker",
                        speaker=series.display_name,
                        chart_intent="bar_categorical",
                        title=(
                            f"{prefix} — Word count — "
                            f"{series.display_name} across sessions"
                        ),
                        x_label="Session",
                        y_label="Word count",
                        categories=list(series.categories),
                        values=list(series.values),
                    ),
                    chart_type="bar",
                )

            cross_seg = collect_stats_cross_session_speaker_segment_count_series(
                ptr,
                ctx.transcript_set,
                cmap,
            )
            for series in cross_seg:
                sid = int(series.canonical_speaker_id)
                svc.save_chart(
                    BarCategoricalSpec(
                        viz_id=(
                            f"group.stats.cross_session_speaker."
                            f"segment_count.speaker_{sid}"
                        ),
                        module=self.agg_id,
                        name=f"stats_cross_session_segment_count_{sid}"[:80],
                        scope="speaker",
                        speaker=series.display_name,
                        chart_intent="bar_categorical",
                        title=(
                            f"{prefix} — Segment count across sessions — "
                            f"{series.display_name}"
                        ),
                        x_label="Session",
                        y_label="Segment count",
                        categories=list(series.categories),
                        values=list(series.values),
                    ),
                    chart_type="bar",
                )

        sp = outcome.get("stats_pooled")
        if isinstance(sp, dict) and sp.get("schema_version") == 1:
            tw = int(sp.get("total_words") or 0)
            ts = int(sp.get("total_segments") or 0)
            td = float(sp.get("total_duration") or 0)
            if tw > 0 or ts > 0 or td > 0:
                svc.save_chart(
                    BarCategoricalSpec(
                        viz_id="group.stats.pooled.totals.global",
                        module=self.agg_id,
                        name="stats_pooled_totals",
                        scope="global",
                        chart_intent="bar_categorical",
                        title="Group pooled — corpus totals (words, segments, duration)",
                        x_label="Metric",
                        y_label="Value",
                        categories=[
                            "Total words",
                            "Total segments",
                            "Total duration (s)",
                        ],
                        values=[float(tw), float(ts), td],
                    ),
                    chart_type="bar",
                )

        paths = chart_artifact_paths(svc)
        return paths or None
