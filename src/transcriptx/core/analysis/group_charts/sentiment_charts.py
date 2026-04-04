"""
Group aggregate charts for sentiment.

Families (see ``GROUP_AGGREGATE_CHART_FAMILIES`` in ``registry.py``):

- **session_bars** / **speaker_bars** — means from aggregated rows.
- **temporal_overlay** — cross-session compound lines from member enriched JSON.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.context_guards import (
    should_emit_cross_session_speaker_charts,
    should_emit_temporal_overlay_charts,
)
from transcriptx.core.analysis.group_charts.overlay_series import (
    cap_per_transcript_results_for_overlay,
)
from transcriptx.core.analysis.group_charts.helpers import (
    chart_artifact_paths,
    filter_chartable_speaker_rows,
    member_session_label,
    session_row_label,
)
from transcriptx.core.analysis.group_charts.output_service import (
    GroupChartOutputService,
)
from transcriptx.core.analysis.group_charts.speaker_cross_session import (
    collect_sentiment_cross_session_speaker_series,
)
from transcriptx.core.analysis.group_charts.virtual_path import (
    build_group_virtual_transcript_path,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.utils._path_core import get_base_name
from transcriptx.core.viz.specs import BarCategoricalSpec, LineTimeSeriesSpec
from transcriptx.io import load_transcript

_PREFIX = "Group aggregate (sentiment summary, not time series)"


def _load_member_sentiment_segments(
    result: PerTranscriptResult,
) -> List[Dict[str, Any]]:
    path = (
        Path(result.output_dir)
        / "sentiment"
        / "data"
        / "global"
        / f"{get_base_name(result.transcript_path)}_with_sentiment.json"
    )
    if not path.is_file():
        return []
    data = load_transcript(str(path))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        segs = data.get("segments")
        if isinstance(segs, list):
            return segs
    return []


def _segment_compound(seg: Dict[str, Any]) -> Optional[float]:
    sent = seg.get("sentiment")
    if isinstance(sent, dict):
        c = sent.get("compound")
        if isinstance(c, (int, float)) and not isinstance(c, bool):
            return float(c)
    return None


def generate_group_sentiment_temporal_overlay(
    output_service: GroupChartOutputService,
    per_transcript_results: Sequence[PerTranscriptResult],
    transcript_set: TranscriptSet,
    *,
    title_prefix: str | None = None,
) -> None:
    """Cross-session compound lines; see ``docs/group_charts_sentiment_temporal_contract.md``."""

    def _tp(title: str) -> str:
        if not title_prefix:
            return title
        return f"{title_prefix} — {title}"

    ordered = cap_per_transcript_results_for_overlay(per_transcript_results)

    temporal_series: List[Dict[str, Any]] = []
    for result in ordered:
        segs = _load_member_sentiment_segments(result)
        if not segs:
            continue
        raw_starts = [
            float(s.get("start") or 0)
            for s in segs
            if isinstance(s, dict) and isinstance(s.get("start"), (int, float))
        ]
        t0 = min(raw_starts) if raw_starts else 0.0
        sess_label = member_session_label(result, transcript_set)
        times: List[float] = []
        y_vals: List[float] = []
        for seg in segs:
            if not isinstance(seg, dict):
                continue
            c = _segment_compound(seg)
            if c is None:
                continue
            st = seg.get("start", 0)
            if not isinstance(st, (int, float)):
                st = 0
            times.append((float(st) - t0) / 60.0)
            y_vals.append(c)
        if y_vals:
            temporal_series.append({"name": sess_label, "x": times, "y": y_vals})

    if temporal_series:
        output_service.save_chart(
            LineTimeSeriesSpec(
                viz_id="group.sentiment.temporal_overlay.global",
                module="sentiment",
                name="temporal_overlay",
                scope="global",
                chart_intent="line_timeseries",
                title=_tp(
                    "Compound sentiment — cross-session overlay; session-relative minutes"
                ),
                x_label="Session-relative minutes from first segment",
                y_label="Compound sentiment",
                markers=True,
                series=temporal_series,
            ),
            chart_type="temporal",
        )


_SESSION_FIELDS = ("compound_mean", "pos_mean", "neu_mean", "neg_mean")
_SPEAKER_FIELDS = ("compound_mean", "pos_mean", "neu_mean", "neg_mean", "segment_count")


class SentimentGroupChartGenerator:
    agg_id = "sentiment"

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        session_rows = outcome.get("session_rows") or []
        if len(session_rows) < 1:
            return False
        for row in session_rows:
            for f in _SESSION_FIELDS:
                v = row.get(f)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    return True
        spk = filter_chartable_speaker_rows(outcome.get("speaker_rows") or [])
        return len(spk) > 0

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        session_rows = list(outcome.get("session_rows") or [])
        session_rows.sort(key=lambda r: r.get("order_index", 0))
        speaker_rows = outcome.get("speaker_rows") or []

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

        for field in _SESSION_FIELDS:
            vals = [float(r.get(field) or 0) for r in session_rows]
            if not any(vals):
                continue
            svc.save_chart(
                BarCategoricalSpec(
                    viz_id=f"group.sentiment.session.{field}",
                    module=self.agg_id,
                    name=f"group_session_{field}",
                    scope="global",
                    chart_intent="bar_categorical",
                    title=f"{_PREFIX} — {field.replace('_', ' ').title()} by Session",
                    x_label="Session",
                    y_label=field.replace("_", " ").title(),
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
            for field in _SPEAKER_FIELDS:
                vals = [float(r.get(field) or 0) for r in eligible]
                if not any(vals):
                    continue
                svc.save_chart(
                    BarCategoricalSpec(
                        viz_id=f"group.sentiment.speakers.{field}",
                        module=self.agg_id,
                        name=f"group_speakers_{field}",
                        scope="global",
                        chart_intent="bar_categorical",
                        title=f"{_PREFIX} — {field.replace('_', ' ').title()} by Speaker",
                        x_label="Speaker",
                        y_label=field.replace("_", " ").title(),
                        categories=names,
                        values=vals,
                    ),
                    chart_type="bar",
                )

        if (
            should_emit_temporal_overlay_charts(self.agg_id, ctx.per_transcript_results)
            and ctx.per_transcript_results
        ):
            generate_group_sentiment_temporal_overlay(
                svc,
                ctx.per_transcript_results,
                ctx.transcript_set,
                title_prefix=_PREFIX,
            )

        if (
            should_emit_cross_session_speaker_charts(
                self.agg_id, ctx.canonical_speaker_map
            )
            and ctx.per_transcript_results
        ):
            cmap = ctx.canonical_speaker_map
            assert cmap is not None
            cross = collect_sentiment_cross_session_speaker_series(
                ctx.per_transcript_results,
                ctx.transcript_set,
                cmap,
            )
            for series in cross:
                sid = int(series.canonical_speaker_id)
                svc.save_chart(
                    BarCategoricalSpec(
                        viz_id=f"group.sentiment.cross_session_speaker.speaker_{sid}",
                        module=self.agg_id,
                        name=f"group_cross_session_speaker_{sid}"[:80],
                        scope="speaker",
                        speaker=series.display_name,
                        chart_intent="bar_categorical",
                        title=(
                            f"{_PREFIX} — Sentiment (compound) — "
                            f"{series.display_name} across sessions"
                        ),
                        x_label="Session",
                        y_label="Compound mean",
                        categories=list(series.categories),
                        values=list(series.values),
                    ),
                    chart_type="bar",
                )

        out = chart_artifact_paths(svc)
        return out or None
