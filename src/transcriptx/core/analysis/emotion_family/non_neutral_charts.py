"""Derived non-neutral bar-chart series for emotion-family classifier modules.

Presentation-only: does not affect result schema, semantics, fingerprints, or
aggregation-cache keys.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping

from transcriptx.core.analysis.emotion_family.errors import NonNeutralChartInputError
from transcriptx.core.utils.logger import log_warning
from transcriptx.core.viz.specs import BarCategoricalSpec
from transcriptx.utils.text_utils import is_analysis_speaker_label

OrderMode = Literal["alpha", "top_n"]

SaveChartFn = Callable[[BarCategoricalSpec], None]


@dataclass(frozen=True)
class NonNeutralBarSeries:
    """Count and share series over the same selected non-neutral categories."""

    categories: tuple[str, ...]
    counts: tuple[float, ...]
    shares: tuple[float, ...]
    non_neutral_total: float


def _is_neutral_key(key: object) -> bool:
    return str(key).casefold() == "neutral"


def _coerce_count_value(label: object, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NonNeutralChartInputError(
            f"invalid count for {label!r}: expected finite non-negative number, "
            f"got {type(value).__name__}"
        )
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise NonNeutralChartInputError(
            f"invalid count for {label!r}: expected finite non-negative number, "
            f"got {value!r}"
        )
    return number


def _validate_top_n(top_n: object) -> int:
    if isinstance(top_n, bool) or not isinstance(top_n, int) or top_n < 1:
        raise NonNeutralChartInputError(
            f"top_n must be a positive int (>= 1), got {top_n!r}"
        )
    return top_n


def build_non_neutral_bar_series(
    counts: Mapping[str, Any],
    *,
    order: OrderMode,
    top_n: int = 15,
) -> NonNeutralBarSeries | None:
    """Build exclude-neutral count/share series from a label-count mapping.

    - Never mutates ``counts``.
    - Removes neutral keys case-insensitively.
    - Drops zero-valued entries before ranking/emission.
    - Fail-closed on negative, NaN, infinite, boolean, or non-numeric values.
    - Share denominator ``T`` is the sum of all positive non-neutral counts
      before category truncation; truncated share bars may therefore sum to
      less than 1.
    - Returns ``None`` when the non-neutral total is zero.
    """
    if order not in ("alpha", "top_n"):
        raise NonNeutralChartInputError(f"unsupported order mode: {order!r}")
    if order == "top_n":
        top_n = _validate_top_n(top_n)

    cleaned: dict[str, float] = {}
    for raw_key, raw_value in counts.items():
        if _is_neutral_key(raw_key):
            continue
        label = str(raw_key)
        value = _coerce_count_value(label, raw_value)
        if value == 0.0:
            continue
        cleaned[label] = value

    total = float(sum(cleaned.values()))
    if total == 0.0:
        return None

    if order == "alpha":
        categories = tuple(sorted(cleaned.keys()))
    else:
        ranked = sorted(cleaned.items(), key=lambda kv: (-kv[1], kv[0]))
        categories = tuple(label for label, _ in ranked[:top_n])

    count_values = tuple(cleaned[label] for label in categories)
    share_values = tuple(count / total for count in count_values)
    return NonNeutralBarSeries(
        categories=categories,
        counts=count_values,
        shares=share_values,
        non_neutral_total=total,
    )


def save_chart_isolated(
    save_chart: SaveChartFn,
    spec: BarCategoricalSpec,
    *,
    log_prefix: str,
) -> None:
    """Save one chart; failures are logged and do not propagate."""
    try:
        save_chart(spec)
    except Exception as exc:
        detail = f"{spec.viz_id}"
        if spec.speaker:
            detail = f"{detail} speaker={spec.speaker}"
        log_warning(log_prefix, f"chart save failed ({detail}): {exc}")


def emit_non_neutral_bar_charts(
    *,
    counts: Mapping[str, Any],
    order: OrderMode,
    module: str,
    log_prefix: str,
    save_chart: SaveChartFn,
    count_viz_id: str,
    share_viz_id: str,
    count_name: str,
    share_name: str,
    count_title: str,
    share_title: str,
    scope: Literal["global", "speaker"],
    speaker: str | None = None,
    top_n: int = 15,
) -> None:
    """Emit exclude-neutral count and share charts for one scope, failure-isolated."""
    try:
        series = build_non_neutral_bar_series(counts, order=order, top_n=top_n)
    except NonNeutralChartInputError as exc:
        log_warning(
            log_prefix,
            f"non-neutral chart skipped ({count_viz_id}"
            f"{f' speaker={speaker}' if speaker else ''}): {exc}",
        )
        return
    if series is None:
        return

    count_spec = BarCategoricalSpec(
        viz_id=count_viz_id,
        module=module,
        name=count_name,
        scope=scope,
        speaker=speaker,
        chart_intent="bar_categorical",
        title=count_title,
        x_label="Label",
        y_label="Count",
        categories=list(series.categories),
        values=list(series.counts),
    )
    share_spec = BarCategoricalSpec(
        viz_id=share_viz_id,
        module=module,
        name=share_name,
        scope=scope,
        speaker=speaker,
        chart_intent="bar_categorical",
        title=share_title,
        x_label="Label",
        y_label="Share of non-neutral",
        categories=list(series.categories),
        values=list(series.shares),
    )
    save_chart_isolated(save_chart, count_spec, log_prefix=log_prefix)
    save_chart_isolated(save_chart, share_spec, log_prefix=log_prefix)


def iter_named_speaker_label_counts(
    speaker_stats: Mapping[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """Yield named speakers with non-empty label_counts mappings."""
    out: list[tuple[str, dict[str, Any]]] = []
    for speaker, stats in (speaker_stats or {}).items():
        if not is_analysis_speaker_label(speaker):
            continue
        label_counts = (stats or {}).get("label_counts") or {}
        if not label_counts:
            continue
        out.append((str(speaker), dict(label_counts)))
    return out
