from __future__ import annotations

from typing import Any, Dict, List

from transcriptx.core.utils.viz_ids import (  # type: ignore[import-untyped]
    VIZ_VOICE_DRIFT_TIMELINE_SPEAKER,
    VIZ_VOICE_MISMATCH_SCATTER_GLOBAL,
    VIZ_VOICE_MISMATCH_TIMELINE_GLOBAL,
    VIZ_VOICE_TENSION_CURVE_GLOBAL,
)
from transcriptx.core.viz.specs import (  # type: ignore[import-untyped]
    LineTimeSeriesSpec,
    ScatterSeries,
    ScatterSpec,
)


def tension_curve_spec(series_rows: List[Dict[str, Any]]) -> LineTimeSeriesSpec | None:
    if not series_rows:
        return None
    xs = [float(r.get("bin_start_s", 0.0)) for r in series_rows]
    smooth = [float(r.get("tension_smooth", 0.0)) for r in series_rows]
    raw = [float(r.get("tension_raw", 0.0)) for r in series_rows]
    return LineTimeSeriesSpec(
        viz_id=VIZ_VOICE_TENSION_CURVE_GLOBAL,
        module="voice_tension",
        name="tension_curve",
        scope="global",
        chart_intent="line_timeseries",
        title="Conversation Tension Curve",
        x_label="Time (seconds)",
        y_label="Tension (a.u.)",
        markers=False,
        series=[
            {"name": "tension_smooth", "x": xs, "y": smooth},
            {"name": "tension_raw", "x": xs, "y": raw},
        ],
    )


def mismatch_scatter_spec(points: List[Dict[str, Any]]) -> ScatterSpec | None:
    if not points:
        return None
    x = [float(p.get("sentiment", 0.0)) for p in points]
    y = [float(p.get("arousal", 0.0)) for p in points]
    text = [
        str(p.get("hover", p.get("text", "")) or "")[:300]
        for p in points
    ]
    return ScatterSpec(
        viz_id=VIZ_VOICE_MISMATCH_SCATTER_GLOBAL,
        module="voice_mismatch",
        name="sentiment_vs_arousal",
        scope="global",
        chart_intent="scatter",
        title="Sentiment vs Voice Arousal",
        x_label="Text sentiment (VADER compound)",
        y_label="Voice arousal (proxy)",
        x=x,
        y=y,
        text=text,
        marker={"opacity": 0.6, "size": 6},
        mode="markers",
    )


def mismatch_timeline_spec(rows: List[Dict[str, Any]]) -> LineTimeSeriesSpec | None:
    if not rows:
        return None
    xs = [float(r.get("start_s", 0.0)) for r in rows]
    ys = [float(r.get("mismatch_score", 0.0)) for r in rows]
    return LineTimeSeriesSpec(
        viz_id=VIZ_VOICE_MISMATCH_TIMELINE_GLOBAL,
        module="voice_mismatch",
        name="mismatch_timeline",
        scope="global",
        chart_intent="line_timeseries",
        title="Tone–Text Mismatch Timeline",
        x_label="Time (seconds)",
        y_label="Mismatch score",
        markers=True,
        series=[{"name": "mismatch", "x": xs, "y": ys}],
    )


def drift_timeline_spec(speaker: str, rows: List[Dict[str, Any]]) -> LineTimeSeriesSpec | None:
    if not rows:
        return None
    xs = [float(r.get("start_s", 0.0)) for r in rows]
    ys = [float(r.get("drift_score", 0.0)) for r in rows]
    return LineTimeSeriesSpec(
        viz_id=VIZ_VOICE_DRIFT_TIMELINE_SPEAKER,
        module="voice_fingerprint",
        name="drift_timeline",
        scope="speaker",
        speaker=str(speaker),
        chart_intent="line_timeseries",
        title=f"Voice Drift Timeline: {speaker}",
        x_label="Time (seconds)",
        y_label="Drift score",
        markers=True,
        series=[{"name": "drift", "x": xs, "y": ys}],
    )

