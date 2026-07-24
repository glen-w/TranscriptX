"""Group charts for topic_shift — cohort-safe session bars + marker overlays."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.context_guards import (
    should_emit_temporal_overlay_charts,
)
from transcriptx.core.analysis.group_charts.helpers import (
    chart_artifact_paths,
    make_group_output_service,
    member_session_label,
    session_row_label,
)
from transcriptx.core.analysis.group_charts.overlay_series import (
    cap_per_transcript_results_for_overlay,
)
from transcriptx.core.analysis.topic_shift.events_io import load_topic_shift_events
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.utils.viz_ids import VIZ_GROUP_TOPIC_SHIFT_RATE
from transcriptx.core.viz.specs import BarCategoricalSpec, LineTimeSeriesSpec

VIZ_GROUP_TOPIC_SHIFT_OVERLAY = "group.topic_shift.temporal_overlay.global"


def _primary_key(session_rows: List[Dict[str, Any]], pooled: Dict[str, Any]) -> str:
    key = str(pooled.get("comparable_key") or "")
    if key:
        return key
    by_key: Dict[str, List[Dict[str, Any]]] = {}
    for row in session_rows:
        if not row.get("included_in_comparison"):
            continue
        by_key.setdefault(
            str(row.get("provenance_compatibility_key") or ""), []
        ).append(row)
    if not by_key:
        return ""
    return max(by_key.keys(), key=lambda k: (len(by_key[k]), k))


def _events_path(result: PerTranscriptResult) -> Path:
    return (
        Path(result.output_dir)
        / "topic_shift"
        / "data"
        / "global"
        / "topic_shift.events.json"
    )


def generate_group_topic_shift_temporal_overlay(
    output_service: Any,
    per_transcript_results: Sequence[PerTranscriptResult],
    transcript_set: TranscriptSet,
    *,
    title_prefix: str | None = None,
) -> None:
    """Cross-session topic-shift markers (unwrap-aware; session-relative minutes)."""

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
        events = load_topic_shift_events(path)
        if not events:
            continue
        raw_starts = [float(e.time_start) for e in events]
        t0 = min(raw_starts) if raw_starts else 0.0
        sess_label = member_session_label(result, transcript_set)
        times: List[float] = []
        y_vals: List[float] = []
        for e in events:
            ts = float(e.time_start)
            times.append((ts - t0) / 60.0)
            strength = None
            evid_list = e.evidence if isinstance(e.evidence, list) else []
            for item in evid_list:
                if isinstance(item, dict) and "normalized_strength" in item:
                    try:
                        strength = float(item["normalized_strength"])
                    except (TypeError, ValueError):
                        strength = None
                    break
            if strength is None:
                strength = float(e.severity) if e.severity is not None else 1.0
            y_vals.append(strength)
        if y_vals:
            temporal_series.append({"name": sess_label, "x": times, "y": y_vals})

    if temporal_series:
        output_service.save_chart(
            LineTimeSeriesSpec(
                viz_id=VIZ_GROUP_TOPIC_SHIFT_OVERLAY,
                module="topic_shift",
                name="temporal_overlay",
                scope="global",
                chart_intent="line_timeseries",
                title=_tp(
                    "Topic shifts — cross-session overlay; session-relative minutes"
                ),
                x_label="Session-relative minutes from first plotted shift",
                y_label="Shift strength (backend-local)",
                markers=True,
                series=temporal_series,
            ),
            chart_type="temporal",
        )


class TopicShiftGroupChartGenerator:
    """Session bars within one provenance cohort; missing/abstained never coerced to 0."""

    agg_id = "topic_shift"

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        session_rows = list(outcome.get("session_rows") or [])
        pooled = outcome.get("topic_shift_pooled") or {}
        primary = _primary_key(session_rows, pooled)
        if not primary:
            return False
        return any(
            r.get("included_in_comparison")
            and str(r.get("provenance_compatibility_key") or "") == primary
            for r in session_rows
        )

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        session_rows = list(outcome.get("session_rows") or [])
        pooled = outcome.get("topic_shift_pooled") or {}
        primary = _primary_key(session_rows, pooled)
        if not primary:
            return None

        cohort = [
            r
            for r in session_rows
            if r.get("included_in_comparison")
            and str(r.get("provenance_compatibility_key") or "") == primary
        ]
        if not cohort:
            return None
        cohort.sort(key=lambda r: r.get("order_index", 0))

        svc = make_group_output_service(
            ctx, module_name=self.agg_id, agg_id=self.agg_id
        )
        incompatible = int(pooled.get("incompatible_member_count") or 0)
        excluded = int(pooled.get("excluded_abstention_count") or 0)
        note = f"provenance={primary}"
        if incompatible:
            note += f"; excluded incompatible={incompatible}"
        if excluded:
            note += f"; excluded abstentions={excluded}"
        prefix = "Group topic shifts (comparable cohort only; rates not cross-backend)"

        for metric, y_label, viz_suffix, viz_id in (
            (
                "shifts_per_hour",
                "Shifts per hour",
                "shifts_per_hour",
                VIZ_GROUP_TOPIC_SHIFT_RATE,
            ),
            (
                "n_shifts",
                "Shift count (supporting)",
                "n_shifts",
                "group.topic_shift.session.n_shifts",
            ),
            (
                "median_span_duration",
                "Median span duration (s)",
                "median_span_duration",
                "group.topic_shift.session.median_span_duration",
            ),
            (
                "longest_span_duration",
                "Longest span duration (s)",
                "longest_span_duration",
                "group.topic_shift.session.longest_span_duration",
            ),
        ):
            labels: List[str] = []
            vals: List[float] = []
            for row in cohort:
                raw = row.get(metric)
                if not isinstance(raw, (int, float)):
                    # Intentionally skip nulls — do not coerce to 0
                    continue
                labels.append(session_row_label(row, ctx.transcript_set))
                vals.append(float(raw))
            if not vals:
                continue
            svc.save_chart(
                BarCategoricalSpec(
                    viz_id=viz_id,
                    module=self.agg_id,
                    name=f"group_session_{viz_suffix}"[:80],
                    scope="global",
                    chart_intent="bar_categorical",
                    title=f"{prefix} — {y_label} ({note})",
                    x_label="Session",
                    y_label=y_label,
                    categories=labels,
                    values=vals,
                ),
                chart_type="bar",
            )

        if should_emit_temporal_overlay_charts(self.agg_id, ctx.per_transcript_results):
            generate_group_topic_shift_temporal_overlay(
                svc,
                ctx.per_transcript_results,
                ctx.transcript_set,
                title_prefix=prefix,
            )

        out = chart_artifact_paths(svc)
        return out or None
