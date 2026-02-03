"""Chart generation helpers for affect_tension analysis."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.speaker_extraction import (
    group_segments_by_speaker,
    get_speaker_display_name,
)
from transcriptx.core.viz.specs import (
    BarCategoricalSpec,
    HeatmapMatrixSpec,
    LineTimeSeriesSpec,
)
from transcriptx.core.utils.viz_ids import (
    VIZ_AFFECT_TENSION_AVG_ENTROPY_GLOBAL,
    VIZ_AFFECT_TENSION_AVG_VOLATILITY_GLOBAL,
    VIZ_AFFECT_TENSION_DERIVED_INSTITUTIONAL_TONE_GLOBAL,
    VIZ_AFFECT_TENSION_DERIVED_POLITE_TENSION_GLOBAL,
    VIZ_AFFECT_TENSION_DERIVED_SUPPRESSED_CONFLICT_GLOBAL,
    VIZ_AFFECT_TENSION_ENTROPY_TIMESERIES_GLOBAL,
    VIZ_AFFECT_TENSION_ENTROPY_VOLATILITY_TIMESERIES_GLOBAL,
    VIZ_AFFECT_TENSION_ENTROPY_VOLATILITY_TIMESERIES_SPEAKER,
    VIZ_AFFECT_TENSION_MISMATCH_HEATMAP_GLOBAL,
    VIZ_AFFECT_TENSION_MISMATCH_RATE_GLOBAL,
    VIZ_AFFECT_TENSION_MISMATCH_TIMESERIES_GLOBAL,
    VIZ_AFFECT_TENSION_VOLATILITY_TIMESERIES_GLOBAL,
)
from transcriptx.utils.text_utils import is_named_speaker

logger = get_logger()

MODULE_NAME = "affect_tension"
MAX_SPEAKERS_BAR = 20
MAX_SPEAKERS_TIMESERIES = 10
INCLUDE_GLOBAL = True

# Heuristic threshold for "high entropy" flags when no mismatch_type is provided.
HIGH_ENTROPY_THRESHOLD = 2.0


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values: Iterable[Optional[float]]) -> Optional[float]:
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return sum(filtered) / len(filtered)


def _extract_start_seconds(segment: Dict[str, Any]) -> Optional[float]:
    """Return start time in seconds if confidently normalizable."""
    start_s = _safe_float(segment.get("start_s"))
    if start_s is not None:
        return start_s

    start_ms = segment.get("start_ms")
    if start_ms is not None:
        start_ms_val = _safe_float(start_ms)
        if start_ms_val is not None:
            return start_ms_val / 1000.0

    start_time = _safe_float(segment.get("start_time"))
    if start_time is not None:
        return start_time

    start_unit = segment.get("start_unit")
    start = _safe_float(segment.get("start"))
    if start is None:
        return None
    if start_unit in {"ms", "millis", "milliseconds"}:
        return start / 1000.0
    if start_unit in {"s", "sec", "seconds"}:
        return start
    # Heuristic: if start is small, treat as seconds; otherwise fall back to index.
    if start <= 1e4:
        return start
    return None


def _group_segments(
    segments: List[Dict[str, Any]],
    *,
    max_speakers: int,
) -> Tuple[List[str], Dict[str, List[Dict[str, Any]]]]:
    grouped = group_segments_by_speaker(segments)
    display_grouped: Dict[str, List[Dict[str, Any]]] = {}

    for key, segs in grouped.items():
        if not segs:
            continue
        speaker = get_speaker_display_name(key, segs, segments)
        if not speaker or not is_named_speaker(speaker):
            continue
        display_grouped.setdefault(speaker, []).extend(segs)

    ordered = sorted(
        display_grouped.items(),
        key=lambda item: (-len(item[1]), item[0]),
    )
    if max_speakers > 0:
        ordered = ordered[:max_speakers]
    speakers = [name for name, _ in ordered]
    return speakers, {name: segs for name, segs in ordered}


def _rate(
    segments: Sequence[Dict[str, Any]],
    predicate: Callable[[Dict[str, Any]], bool],
) -> Optional[float]:
    total = len(segments)
    if total == 0:
        return None
    count = sum(1 for seg in segments if predicate(seg))
    return count / total


def _build_series(
    segments: Sequence[Dict[str, Any]],
    y_extractor: Callable[[Dict[str, Any]], Optional[float]],
) -> Tuple[List[float], List[float]]:
    xs: List[float] = []
    ys: List[float] = []
    for idx, seg in enumerate(segments):
        y_val = y_extractor(seg)
        if y_val is None:
            continue
        x_val = _extract_start_seconds(seg)
        if x_val is None:
            x_val = float(idx)
        xs.append(float(x_val))
        ys.append(float(y_val))
    return xs, ys


def build_derived_indices_charts(
    derived_indices: Dict[str, Any],
    segments: List[Dict[str, Any]],
    base_name: str,
    module_name: str = MODULE_NAME,
) -> List[BarCategoricalSpec]:
    specs: List[BarCategoricalSpec] = []
    if not segments:
        return specs

    speakers, speaker_segments = _group_segments(
        segments, max_speakers=MAX_SPEAKERS_BAR
    )
    derived_by_speaker = derived_indices.get("by_speaker", {}) or {}
    derived_global = derived_indices.get("global", {}) or {}

    derived_defs = [
        (
            "polite_tension_index",
            "Polite Tension Index",
            VIZ_AFFECT_TENSION_DERIVED_POLITE_TENSION_GLOBAL,
            "derived_polite_tension_index",
        ),
        (
            "suppressed_conflict_score",
            "Suppressed Conflict Score",
            VIZ_AFFECT_TENSION_DERIVED_SUPPRESSED_CONFLICT_GLOBAL,
            "derived_suppressed_conflict_score",
        ),
        (
            "institutional_tone_affect_delta",
            "Institutional Tone vs Affect Delta",
            VIZ_AFFECT_TENSION_DERIVED_INSTITUTIONAL_TONE_GLOBAL,
            "derived_institutional_tone_delta",
        ),
    ]

    for key, label, viz_id, name in derived_defs:
        categories: List[str] = []
        values: List[float] = []
        for speaker in speakers:
            value = (derived_by_speaker.get(speaker) or {}).get(key)
            if value is None:
                logger.debug(
                    "affect_tension: missing derived index '%s' for speaker '%s'",
                    key,
                    speaker,
                )
                continue
            categories.append(speaker)
            values.append(float(value))
        if INCLUDE_GLOBAL:
            global_value = derived_global.get(key)
            if global_value is not None:
                categories.append("Global")
                values.append(float(global_value))
        if not categories:
            continue
        specs.append(
            BarCategoricalSpec(
                viz_id=viz_id,
                module=module_name,
                name=name,
                scope="global",
                chart_intent="bar_categorical",
                title=f"{label} - {base_name}",
                x_label="Speaker",
                y_label=label,
                categories=categories,
                values=values,
            )
        )

    mismatch_rates: Dict[str, Optional[float]] = {}
    avg_entropy: Dict[str, Optional[float]] = {}
    avg_volatility: Dict[str, Optional[float]] = {}
    for speaker, segs in speaker_segments.items():
        mismatch_rates[speaker] = _rate(
            segs, lambda seg: bool(seg.get("affect_mismatch_posneg"))
        )
        avg_entropy[speaker] = _mean(
            _safe_float(seg.get("emotion_entropy")) for seg in segs
        )
        avg_volatility[speaker] = _mean(
            _safe_float(seg.get("emotion_volatility_proxy")) for seg in segs
        )

    global_mismatch = _rate(
        segments, lambda seg: bool(seg.get("affect_mismatch_posneg"))
    )
    global_entropy = _mean(
        _safe_float(seg.get("emotion_entropy")) for seg in segments
    )
    global_volatility = _mean(
        _safe_float(seg.get("emotion_volatility_proxy")) for seg in segments
    )

    def add_simple_bar(
        name: str,
        label: str,
        viz_id: str,
        values_by_speaker: Dict[str, Optional[float]],
        global_value: Optional[float],
    ) -> None:
        categories: List[str] = []
        values: List[float] = []
        for speaker in speakers:
            value = values_by_speaker.get(speaker)
            if value is None:
                continue
            categories.append(speaker)
            values.append(float(value))
        if INCLUDE_GLOBAL and global_value is not None:
            categories.append("Global")
            values.append(float(global_value))
        if not categories:
            return
        specs.append(
            BarCategoricalSpec(
                viz_id=viz_id,
                module=module_name,
                name=name,
                scope="global",
                chart_intent="bar_categorical",
                title=f"{label} - {base_name}",
                x_label="Speaker",
                y_label=label,
                categories=categories,
                values=values,
            )
        )

    add_simple_bar(
        "mismatch_rate",
        "Mismatch Rate",
        VIZ_AFFECT_TENSION_MISMATCH_RATE_GLOBAL,
        mismatch_rates,
        global_mismatch,
    )
    add_simple_bar(
        "avg_emotion_entropy",
        "Average Emotion Entropy",
        VIZ_AFFECT_TENSION_AVG_ENTROPY_GLOBAL,
        avg_entropy,
        global_entropy,
    )
    add_simple_bar(
        "avg_volatility_proxy",
        "Average Emotion Volatility",
        VIZ_AFFECT_TENSION_AVG_VOLATILITY_GLOBAL,
        avg_volatility,
        global_volatility,
    )

    return specs


def build_dynamics_timeseries_charts(
    segments: List[Dict[str, Any]],
    base_name: str,
    module_name: str = MODULE_NAME,
) -> List[LineTimeSeriesSpec]:
    specs: List[LineTimeSeriesSpec] = []
    if not segments:
        return specs

    entropy_xs, entropy_ys = _build_series(
        segments, lambda seg: _safe_float(seg.get("emotion_entropy"))
    )
    volatility_xs, volatility_ys = _build_series(
        segments, lambda seg: _safe_float(seg.get("emotion_volatility_proxy"))
    )
    mismatch_xs, mismatch_ys = _build_series(
        segments,
        lambda seg: 1.0
        if seg.get("affect_mismatch_posneg") is True
        else 0.0
        if seg.get("affect_mismatch_posneg") is False
        else None,
    )

    if entropy_xs and volatility_xs:
        specs.append(
            LineTimeSeriesSpec(
                viz_id=VIZ_AFFECT_TENSION_ENTROPY_VOLATILITY_TIMESERIES_GLOBAL,
                module=module_name,
                name="entropy_volatility_timeseries",
                scope="global",
                chart_intent="line_timeseries",
                title=f"Emotion Entropy + Volatility Over Time - {base_name}",
                x_label="Time (seconds)",
                y_label="Value",
                markers=False,
                series=[
                    {"name": "Entropy", "x": entropy_xs, "y": entropy_ys},
                    {"name": "Volatility", "x": volatility_xs, "y": volatility_ys},
                ],
            )
        )
    else:
        if entropy_xs:
            specs.append(
                LineTimeSeriesSpec(
                    viz_id=VIZ_AFFECT_TENSION_ENTROPY_TIMESERIES_GLOBAL,
                    module=module_name,
                    name="entropy_timeseries",
                    scope="global",
                    chart_intent="line_timeseries",
                    title=f"Emotion Entropy Over Time - {base_name}",
                    x_label="Time (seconds)",
                    y_label="Entropy",
                    markers=False,
                    series=[{"name": "Entropy", "x": entropy_xs, "y": entropy_ys}],
                )
            )
        if volatility_xs:
            specs.append(
                LineTimeSeriesSpec(
                    viz_id=VIZ_AFFECT_TENSION_VOLATILITY_TIMESERIES_GLOBAL,
                    module=module_name,
                    name="volatility_timeseries",
                    scope="global",
                    chart_intent="line_timeseries",
                    title=f"Emotion Volatility Over Time - {base_name}",
                    x_label="Time (seconds)",
                    y_label="Volatility",
                    markers=False,
                    series=[{"name": "Volatility", "x": volatility_xs, "y": volatility_ys}],
                )
            )

    if mismatch_xs:
        specs.append(
            LineTimeSeriesSpec(
                viz_id=VIZ_AFFECT_TENSION_MISMATCH_TIMESERIES_GLOBAL,
                module=module_name,
                name="mismatch_timeseries",
                scope="global",
                chart_intent="line_timeseries",
                title=f"Mismatch Flags Over Time - {base_name}",
                x_label="Time (seconds)",
                y_label="Mismatch (0/1)",
                markers=False,
                series=[{"name": "Mismatch", "x": mismatch_xs, "y": mismatch_ys}],
            )
        )

    speakers, speaker_segments = _group_segments(
        segments, max_speakers=MAX_SPEAKERS_TIMESERIES
    )
    for speaker in speakers:
        segs = speaker_segments.get(speaker, [])
        if not segs:
            continue
        sp_entropy_xs, sp_entropy_ys = _build_series(
            segs, lambda seg: _safe_float(seg.get("emotion_entropy"))
        )
        sp_vol_xs, sp_vol_ys = _build_series(
            segs, lambda seg: _safe_float(seg.get("emotion_volatility_proxy"))
        )
        if not sp_entropy_xs and not sp_vol_xs:
            continue
        series: List[Dict[str, Any]] = []
        if sp_entropy_xs:
            series.append({"name": "Entropy", "x": sp_entropy_xs, "y": sp_entropy_ys})
        if sp_vol_xs:
            series.append({"name": "Volatility", "x": sp_vol_xs, "y": sp_vol_ys})
        specs.append(
            LineTimeSeriesSpec(
                viz_id=VIZ_AFFECT_TENSION_ENTROPY_VOLATILITY_TIMESERIES_SPEAKER,
                module=module_name,
                name="entropy_volatility_timeseries",
                scope="speaker",
                speaker=speaker,
                chart_intent="line_timeseries",
                title=f"Emotion Entropy + Volatility - {speaker}",
                x_label="Time (seconds)",
                y_label="Value",
                markers=False,
                series=series,
            )
        )

    return specs


def build_tension_summary_heatmap(
    derived_indices: Dict[str, Any],
    segments: List[Dict[str, Any]],
    base_name: str,
    module_name: str = MODULE_NAME,
) -> Optional[HeatmapMatrixSpec]:
    if not segments:
        return None

    speakers, speaker_segments = _group_segments(
        segments, max_speakers=MAX_SPEAKERS_BAR
    )
    if not speakers and not INCLUDE_GLOBAL:
        return None

    mismatch_type_labels = sorted(
        {
            str(seg.get("mismatch_type"))
            for seg in segments
            if seg.get("mismatch_type")
        }
    )
    if mismatch_type_labels:
        categories = mismatch_type_labels

        def category_rate(segs: List[Dict[str, Any]], category: str) -> float:
            return float(
                _rate(segs, lambda seg: str(seg.get("mismatch_type")) == category) or 0.0
            )

        z_rows: List[List[float]] = []
        y_labels: List[str] = []
        for speaker in speakers:
            segs = speaker_segments.get(speaker, [])
            if not segs:
                continue
            y_labels.append(speaker)
            z_rows.append([category_rate(segs, cat) for cat in categories])
        if INCLUDE_GLOBAL:
            y_labels.append("Global")
            z_rows.append([category_rate(segments, cat) for cat in categories])
        if z_rows:
            return HeatmapMatrixSpec(
                viz_id=VIZ_AFFECT_TENSION_MISMATCH_HEATMAP_GLOBAL,
                module=module_name,
                name="mismatch_heatmap",
                scope="global",
                chart_intent="heatmap_matrix",
                title=f"Mismatch Type Rates by Speaker - {base_name}",
                x_label="Mismatch Type",
                y_label="Speaker",
                z=z_rows,
                x_labels=categories,
                y_labels=y_labels,
            )

    flag_categories: List[Tuple[str, Callable[[Dict[str, Any]], bool]]] = [
        ("posneg_mismatch", lambda seg: bool(seg.get("affect_mismatch_posneg"))),
        ("trust_neutral", lambda seg: bool(seg.get("affect_trust_neutral"))),
        (
            "high_entropy_and_mismatch",
            lambda seg: bool(seg.get("affect_mismatch_posneg"))
            and (
                (ent := _safe_float(seg.get("emotion_entropy"))) is not None
                and ent >= HIGH_ENTROPY_THRESHOLD
            ),
        ),
    ]

    z_rows = []
    y_labels = []
    for speaker in speakers:
        segs = speaker_segments.get(speaker, [])
        if not segs:
            continue
        y_labels.append(speaker)
        z_rows.append(
            [
                float(_rate(segs, predicate) or 0.0)
                for _, predicate in flag_categories
            ]
        )
    if INCLUDE_GLOBAL:
        y_labels.append("Global")
        z_rows.append(
            [
                float(_rate(segments, predicate) or 0.0)
                for _, predicate in flag_categories
            ]
        )
    if z_rows and any(any(val > 0 for val in row) for row in z_rows):
        return HeatmapMatrixSpec(
            viz_id=VIZ_AFFECT_TENSION_MISMATCH_HEATMAP_GLOBAL,
            module=module_name,
            name="mismatch_heatmap",
            scope="global",
            chart_intent="heatmap_matrix",
            title=f"Mismatch Category Rates by Speaker - {base_name}",
            x_label="Mismatch Category",
            y_label="Speaker",
            z=z_rows,
            x_labels=[label for label, _ in flag_categories],
            y_labels=y_labels,
        )

    derived_by_speaker = derived_indices.get("by_speaker", {}) or {}
    derived_global = derived_indices.get("global", {}) or {}

    mismatch_rates = {
        speaker: _rate(segs, lambda seg: bool(seg.get("affect_mismatch_posneg")))
        for speaker, segs in speaker_segments.items()
    }
    avg_entropy = {
        speaker: _mean(_safe_float(seg.get("emotion_entropy")) for seg in segs)
        for speaker, segs in speaker_segments.items()
    }
    avg_volatility = {
        speaker: _mean(_safe_float(seg.get("emotion_volatility_proxy")) for seg in segs)
        for speaker, segs in speaker_segments.items()
    }

    metrics = [
        ("polite_tension_index", "Polite Tension"),
        ("suppressed_conflict_score", "Suppressed Conflict"),
        ("institutional_tone_affect_delta", "Tone-Affect Delta"),
        ("mismatch_rate", "Mismatch Rate"),
        ("avg_entropy", "Avg Entropy"),
        ("avg_volatility", "Avg Volatility"),
    ]

    z_rows = []
    y_labels = []
    for speaker in speakers:
        derived = derived_by_speaker.get(speaker)
        if derived is None:
            logger.debug(
                "affect_tension: missing derived indices for speaker '%s' in heatmap",
                speaker,
            )
            continue
        values = [
            _safe_float(derived.get("polite_tension_index")),
            _safe_float(derived.get("suppressed_conflict_score")),
            _safe_float(derived.get("institutional_tone_affect_delta")),
            mismatch_rates.get(speaker),
            avg_entropy.get(speaker),
            avg_volatility.get(speaker),
        ]
        if any(v is None for v in values):
            continue
        y_labels.append(speaker)
        z_rows.append([float(v) for v in values if v is not None])

    if INCLUDE_GLOBAL:
        values = [
            _safe_float(derived_global.get("polite_tension_index")),
            _safe_float(derived_global.get("suppressed_conflict_score")),
            _safe_float(derived_global.get("institutional_tone_affect_delta")),
            _rate(segments, lambda seg: bool(seg.get("affect_mismatch_posneg"))),
            _mean(_safe_float(seg.get("emotion_entropy")) for seg in segments),
            _mean(_safe_float(seg.get("emotion_volatility_proxy")) for seg in segments),
        ]
        if not any(v is None for v in values):
            y_labels.append("Global")
            z_rows.append([float(v) for v in values if v is not None])

    if not z_rows:
        return None
    return HeatmapMatrixSpec(
        viz_id=VIZ_AFFECT_TENSION_MISMATCH_HEATMAP_GLOBAL,
        module=module_name,
        name="metrics_heatmap",
        scope="global",
        chart_intent="heatmap_matrix",
        title=f"Affect Tension Metrics by Speaker - {base_name}",
        x_label="Metric",
        y_label="Speaker",
        z=z_rows,
        x_labels=[label for _, label in metrics],
        y_labels=y_labels,
    )
