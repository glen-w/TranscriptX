"""Typed dual time-series builders for speaker profile appearances."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, Sequence

from transcriptx.core.speaker_profiles.aggregates import (
    AppearanceRow,
    headline_eligible,
)
from transcriptx.core.speaker_profiles.longitudinal import (
    compute_period_speaking_share,
    dedupe_to_transcript_contributions,
)

TimeSeriesMetric = Literal["words", "turns", "duration_seconds", "speaking_share"]
SeriesKind = Literal["headline", "all"]

_UNKNOWN_SORT = date.max


@dataclass(frozen=True)
class TimeSeriesPoint:
    metric: TimeSeriesMetric
    sort_key: date
    display_label: str
    value: float | None
    source_appearance_ids: tuple[str, ...]
    managed_transcript_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class TimeSeries:
    kind: SeriesKind
    metric: TimeSeriesMetric
    points: tuple[TimeSeriesPoint, ...]


def _bucket_key(row: AppearanceRow) -> tuple[date, str]:
    if row.appearance_date is None:
        return (_UNKNOWN_SORT, "Unknown date")
    return (row.appearance_date, row.appearance_date.isoformat())


def build_time_series(
    appearances: Sequence[AppearanceRow],
    *,
    metric: TimeSeriesMetric,
    kind: SeriesKind,
    include_ignored: bool = False,
    transcript_denominators: dict[str, float] | None = None,
) -> TimeSeries:
    """Build a headline or all series; same-date buckets never mix eligibility."""
    if kind == "headline":
        rows = [
            r
            for r in appearances
            if headline_eligible(r, include_ignored=include_ignored)
        ]
    else:
        rows = list(appearances)

    buckets: dict[tuple[date, str], list[AppearanceRow]] = {}
    for row in rows:
        buckets.setdefault(_bucket_key(row), []).append(row)

    points: list[TimeSeriesPoint] = []
    dens = transcript_denominators or {}
    for sort_key, label in sorted(buckets.keys(), key=lambda k: (k[0], k[1])):
        group = buckets[(sort_key, label)]
        contribs = dedupe_to_transcript_contributions(group)
        ids = tuple(sorted({aid for c in contribs for aid in c.source_appearance_ids}))
        transcript_ids = tuple(c.managed_transcript_id for c in contribs)
        if metric == "speaking_share":
            share = compute_period_speaking_share(contribs, dens)
            value = share.value
        else:
            total = 0.0
            any_value = False
            for c in contribs:
                if metric == "words":
                    total += float(c.words)
                    any_value = True
                elif metric == "turns":
                    total += float(c.turns)
                    any_value = True
                elif metric == "duration_seconds":
                    if c.duration_seconds is not None:
                        total += c.duration_seconds
                        any_value = True
            value = (
                total if any_value else (0.0 if metric in {"words", "turns"} else None)
            )
        points.append(
            TimeSeriesPoint(
                metric=metric,
                sort_key=sort_key,
                display_label=label,
                value=value,
                source_appearance_ids=ids,
                managed_transcript_ids=transcript_ids,
            )
        )
    return TimeSeries(kind=kind, metric=metric, points=tuple(points))


DIRECTORY_TOP_N = 8


@dataclass(frozen=True)
class DirectoryChartSeries:
    """Stacked activity: profile_id or 'Other' → points by date label."""

    metric: Literal["words", "turns"]
    series_by_key: dict[str, tuple[TimeSeriesPoint, ...]]
    ranked_profile_ids: tuple[str, ...]
    other_profile_ids: tuple[str, ...]


def build_directory_activity_chart(
    *,
    profile_rows: dict[str, tuple[AppearanceRow, ...]],
    profile_headline_words: dict[str, int],
    active_profile_ids: Sequence[str],
    include_ignored: bool = False,
    top_n: int = DIRECTORY_TOP_N,
    metric: Literal["words", "turns"] = "words",
) -> DirectoryChartSeries:
    """Rank active profiles by headline words; collapse remainder into Other."""
    ranked = sorted(
        active_profile_ids,
        key=lambda pid: (-int(profile_headline_words.get(pid, 0)), pid),
    )
    top = tuple(ranked[:top_n])
    other_ids = tuple(ranked[top_n:])

    series: dict[str, tuple[TimeSeriesPoint, ...]] = {}
    for pid in top:
        ts = build_time_series(
            profile_rows.get(pid, ()),
            metric=metric,
            kind="headline",
            include_ignored=include_ignored,
        )
        series[pid] = ts.points

    if other_ids:
        combined: list[AppearanceRow] = []
        for pid in other_ids:
            combined.extend(profile_rows.get(pid, ()))
        ts = build_time_series(
            combined,
            metric=metric,
            kind="headline",
            include_ignored=include_ignored,
        )
        series["Other"] = ts.points

    return DirectoryChartSeries(
        metric=metric,
        series_by_key=series,
        ranked_profile_ids=top,
        other_profile_ids=other_ids,
    )
