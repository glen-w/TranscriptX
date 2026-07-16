"""
Group aggregate charts for emotion (session bars + temporal overlay).

Session rows carry ``global_emotions`` (aggregation contract): a dict whose keys must
match ``CANONICAL_EMOTION_LABELS`` exactly — see ``docs/groups/group_charts_emotion_temporal_contract.md``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.context_guards import (
    should_emit_temporal_overlay_charts,
)
from transcriptx.core.analysis.group_charts.helpers import (
    make_group_output_service,
    chart_artifact_paths,
    member_session_label,
    session_row_label,
)
from transcriptx.core.analysis.group_charts.overlay_series import (
    cap_per_transcript_results_for_overlay,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.utils._path_core import get_base_name
from transcriptx.core.viz.specs import BarCategoricalSpec, LineTimeSeriesSpec
from transcriptx.io import load_transcript

# Lowercase labels only; keys in session rows are global_emotions.{label} via nested dict.
CANONICAL_EMOTION_LABELS: Tuple[str, ...] = (
    "joy",
    "sadness",
    "anger",
    "fear",
    "surprise",
    "disgust",
    "neutral",
)

_PREFIX = "Group aggregate (emotion summary by session, not time series)"


def _global_emotions_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = row.get("global_emotions")
    return raw if isinstance(raw, dict) else {}


def _row_value_for_label(row: Dict[str, Any], label: str) -> Optional[float]:
    """Exact key ``label`` under ``global_emotions`` only."""
    ge = _global_emotions_dict(row)
    if label not in ge:
        return None
    v = ge[label]
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def any_canonical_emotion_present(session_rows: Sequence[Dict[str, Any]]) -> bool:
    for row in session_rows:
        ge = _global_emotions_dict(row)
        for label in CANONICAL_EMOTION_LABELS:
            if label in ge:
                return True
    return False


def labels_present_across_sessions(
    session_rows: Sequence[Dict[str, Any]],
) -> List[str]:
    """Canonical labels that appear in at least one session (exact key match)."""
    found: set[str] = set()
    for row in session_rows:
        ge = _global_emotions_dict(row)
        for label in CANONICAL_EMOTION_LABELS:
            if label in ge:
                found.add(label)
    return [lbl for lbl in CANONICAL_EMOTION_LABELS if lbl in found]


def _load_member_emotion_segments(result: PerTranscriptResult) -> List[Dict[str, Any]]:
    path = (
        Path(result.output_dir)
        / "emotion"
        / "data"
        / "global"
        / f"{get_base_name(result.transcript_path)}_with_emotion.json"
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


def segment_emotion_contract_y(seg: Dict[str, Any]) -> Optional[float]:
    """
    Single scalar for ``group.emotion.temporal_overlay.global`` (see emotion temporal contract).

    y = S[p] when p = context_emotion_primary (non-empty str), S = context_emotion_scores (dict),
    and S[p] is numeric. Otherwise None (segment skipped).
    """
    if not isinstance(seg, dict):
        return None
    primary = seg.get("context_emotion_primary")
    if not isinstance(primary, str) or not primary.strip():
        return None
    scores = seg.get("context_emotion_scores")
    if not isinstance(scores, dict):
        return None
    v = scores.get(primary)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def generate_group_emotion_temporal_overlay(
    output_service: GroupChartOutputService,
    per_transcript_results: Sequence[PerTranscriptResult],
    transcript_set: TranscriptSet,
    *,
    title_prefix: str | None = None,
) -> None:
    """
    Cross-session emotion confidence lines; see ``docs/groups/group_charts_emotion_temporal_contract.md``.
    """

    def _tp(title: str) -> str:
        if not title_prefix:
            return title
        return f"{title_prefix} — {title}"

    ordered = cap_per_transcript_results_for_overlay(per_transcript_results)

    temporal_series: List[Dict[str, Any]] = []
    for result in ordered:
        segs = _load_member_emotion_segments(result)
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
            y = segment_emotion_contract_y(seg)
            if y is None:
                continue
            st = seg.get("start", 0)
            if not isinstance(st, (int, float)):
                st = 0
            times.append((float(st) - t0) / 60.0)
            y_vals.append(y)
        if len(y_vals) >= 2:
            temporal_series.append({"name": sess_label, "x": times, "y": y_vals})

    if temporal_series:
        output_service.save_chart(
            LineTimeSeriesSpec(
                viz_id="group.emotion.temporal_overlay.global",
                module="emotion",
                name="temporal_overlay",
                scope="global",
                chart_intent="line_timeseries",
                title=_tp(
                    "Context emotion score (primary label) — cross-session overlay, "
                    "session-relative minutes"
                ),
                x_label="Session-relative minutes from first segment",
                y_label="context_emotion_scores[context_emotion_primary]",
                markers=True,
                series=temporal_series,
            ),
            chart_type="temporal",
        )


class EmotionGroupChartGenerator:
    agg_id = "emotion"

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        session_rows = outcome.get("session_rows") or []
        if len(session_rows) < 1:
            return False
        return any_canonical_emotion_present(session_rows)

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        session_rows = list(outcome.get("session_rows") or [])
        session_rows.sort(key=lambda r: r.get("order_index", 0))
        if not any_canonical_emotion_present(session_rows):
            return None

        svc = make_group_output_service(
            ctx, module_name=self.agg_id, agg_id=self.agg_id
        )
        labels = [session_row_label(r, ctx.transcript_set) for r in session_rows]
        present_labels = labels_present_across_sessions(session_rows)

        for label in present_labels:
            vals: List[float] = []
            for row in session_rows:
                v = _row_value_for_label(row, label)
                vals.append(0.0 if v is None else v)
            if not any(vals):
                continue
            safe = label.replace(".", "_")
            svc.save_chart(
                BarCategoricalSpec(
                    viz_id=f"group.emotion.session.{safe}",
                    module=self.agg_id,
                    name=f"group_session_emotion_{safe}"[:80],
                    scope="global",
                    chart_intent="bar_categorical",
                    title=f"{_PREFIX} — {label} emotion score by session",
                    x_label="Session",
                    y_label=label,
                    categories=labels,
                    values=vals,
                ),
                chart_type="bar",
            )

        if (
            should_emit_temporal_overlay_charts(self.agg_id, ctx.per_transcript_results)
            and ctx.per_transcript_results
        ):
            generate_group_emotion_temporal_overlay(
                svc,
                ctx.per_transcript_results,
                ctx.transcript_set,
                title_prefix=_PREFIX,
            )

        ep = outcome.get("emotion_pooled")
        if isinstance(ep, dict) and ep.get("schema_version") == 1:
            scores = ep.get("emotion_scores")
            if isinstance(scores, dict) and scores:
                ordered = [lbl for lbl in CANONICAL_EMOTION_LABELS if lbl in scores]
                if not ordered:
                    ordered = sorted(scores.keys())
                vals = [float(scores[k]) for k in ordered]
                if any(vals):
                    svc.save_chart(
                        BarCategoricalSpec(
                            viz_id="group.emotion.pooled.profile.global",
                            module=self.agg_id,
                            name="emotion_pooled_profile",
                            scope="global",
                            chart_intent="bar_categorical",
                            title=(
                                "Group pooled — mean global emotion profile "
                                "(unweighted across transcripts)"
                            ),
                            x_label="Emotion",
                            y_label="Score",
                            categories=list(ordered),
                            values=vals,
                        ),
                        chart_type="bar",
                    )

        out = chart_artifact_paths(svc)
        return out or None
