"""Longitudinal trend builders for speaker profile analytics pack."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date
from typing import Literal, Mapping, Sequence

from transcriptx.core.speaker_profiles.aggregates import (
    AppearanceRow,
    finite_valid_duration,
    series_eligible,
)
from transcriptx.core.speaker_profiles.snapshot import TranscriptBundle
from transcriptx.io.speaker_map_resolver import normalize_diarized_id

AnalyticsGrain = Literal["appearance_date", "month", "quarter"]
Availability = Literal["available", "partial", "unavailable"]
InclusionKind = Literal["headline", "all"]

_UNKNOWN_SORT = date.max
_UNKNOWN_PERIOD_ID = "unknown"
_UNKNOWN_LABEL = "Unknown date"


@dataclass(frozen=True)
class TranscriptContribution:
    managed_transcript_id: str
    words: int
    turns: int
    duration_seconds: float | None
    timing_valid_turn_count: int
    source_appearance_ids: tuple[str, ...]
    local_speaker_keys: tuple[str, ...]
    untimed: bool


@dataclass(frozen=True)
class ShareResult:
    value: float | None
    availability: Availability
    evidence_note: str | None
    speaking_share_basis: Literal["duration", "unavailable"]
    numerator_seconds: float | None
    denominator_seconds: float | None


@dataclass(frozen=True)
class SeriesPoint:
    metric: str
    grain: AnalyticsGrain
    period_id: str
    sort_key: date
    display_label: str
    value: float | None
    availability: Availability
    evidence_note: str | None
    source_appearance_ids: tuple[str, ...]
    managed_transcript_ids: tuple[str, ...]
    n_valid_turns: int = 0
    secondary_value: float | None = None


@dataclass(frozen=True)
class TrendCoverage:
    appearance_count: int
    excluded_uncertain_count: int
    ignored_excluded_count: int
    untimed_count: int


@dataclass(frozen=True)
class TrendBundle:
    inclusion: InclusionKind
    grain: AnalyticsGrain
    speaking_minutes: tuple[SeriesPoint, ...]
    speaking_share: tuple[SeriesPoint, ...]
    words: tuple[SeriesPoint, ...]
    turns: tuple[SeriesPoint, ...]
    turn_length_avg: tuple[SeriesPoint, ...]
    turn_length_median: tuple[SeriesPoint, ...]
    speaking_rate_wpm: tuple[SeriesPoint, ...]
    coverage: TrendCoverage
    methodology_codes: tuple[str, ...]
    integrity_warnings: tuple[str, ...] = ()


def period_identity(
    appearance_date: date | None, grain: AnalyticsGrain
) -> tuple[date, str, str]:
    """Return (sort_key, period_id, display_label) — locale/timezone independent."""
    if appearance_date is None:
        return (_UNKNOWN_SORT, _UNKNOWN_PERIOD_ID, _UNKNOWN_LABEL)
    if grain == "appearance_date":
        pid = appearance_date.isoformat()
        return (appearance_date, pid, pid)
    if grain == "month":
        pid = f"{appearance_date.year:04d}-{appearance_date.month:02d}"
        return (date(appearance_date.year, appearance_date.month, 1), pid, pid)
    # quarter
    q = (appearance_date.month - 1) // 3 + 1
    pid = f"{appearance_date.year:04d}-Q{q}"
    month = 3 * (q - 1) + 1
    return (date(appearance_date.year, month, 1), pid, pid)


def dedupe_to_transcript_contributions(
    rows: Sequence[AppearanceRow],
) -> tuple[TranscriptContribution, ...]:
    """Numerator dedupe: unique link_id, then (tid, local_key), sum distinct keys per tid."""
    by_link: dict[str, AppearanceRow] = {}
    for row in sorted(rows, key=lambda r: r.link_id):
        if row.link_id not in by_link:
            by_link[row.link_id] = row
    by_key: dict[tuple[str, str], AppearanceRow] = {}
    for row in sorted(by_link.values(), key=lambda r: r.link_id):
        key = (row.managed_transcript_id, row.local_speaker_key)
        if key not in by_key:
            by_key[key] = row
    by_tid: dict[str, list[AppearanceRow]] = {}
    for row in by_key.values():
        by_tid.setdefault(row.managed_transcript_id, []).append(row)

    contributions: list[TranscriptContribution] = []
    for tid in sorted(by_tid.keys()):
        group = sorted(by_tid[tid], key=lambda r: r.link_id)
        words = sum(r.metrics.words for r in group)
        turns = sum(r.metrics.turns for r in group)
        timing_count = sum(r.metrics.timing_valid_turn_count for r in group)
        dur_parts = [
            r.metrics.duration_seconds
            for r in group
            if r.metrics.duration_seconds is not None
            and math.isfinite(r.metrics.duration_seconds)
        ]
        if dur_parts:
            duration = float(sum(dur_parts))
            if not math.isfinite(duration):
                duration = None
                untimed = True
            else:
                untimed = len(dur_parts) < len(group)
        else:
            duration = None
            untimed = True
        contributions.append(
            TranscriptContribution(
                managed_transcript_id=tid,
                words=words,
                turns=turns,
                duration_seconds=duration,
                timing_valid_turn_count=timing_count,
                source_appearance_ids=tuple(sorted(r.link_id for r in group)),
                local_speaker_keys=tuple(sorted({r.local_speaker_key for r in group})),
                untimed=untimed,
            )
        )
    return tuple(contributions)


def compute_period_speaking_share(
    transcript_contributions: Sequence[TranscriptContribution],
    transcript_denominators: Mapping[str, float],
) -> ShareResult:
    """Shared share math for date/month/quarter — never average daily percentages."""
    num = 0.0
    any_num = False
    missing_timing = 0
    for c in transcript_contributions:
        if c.duration_seconds is not None and math.isfinite(c.duration_seconds):
            num += c.duration_seconds
            any_num = True
        else:
            missing_timing += 1
    denom = 0.0
    seen: set[str] = set()
    for c in transcript_contributions:
        tid = c.managed_transcript_id
        if tid in seen:
            continue
        seen.add(tid)
        d = transcript_denominators.get(tid)
        if d is not None and math.isfinite(d) and d > 0:
            denom += float(d)
    if denom <= 0 or not math.isfinite(denom):
        return ShareResult(
            value=None,
            availability="unavailable",
            evidence_note=(
                "missing_timing:all" if missing_timing else "denom_unavailable"
            ),
            speaking_share_basis="unavailable",
            numerator_seconds=num if any_num else None,
            denominator_seconds=None,
        )
    if not any_num:
        note = f"missing_timing:{missing_timing}/{len(transcript_contributions)}"
        return ShareResult(
            value=None,
            availability="unavailable",
            evidence_note=note,
            speaking_share_basis="unavailable",
            numerator_seconds=None,
            denominator_seconds=denom,
        )
    value = num / denom
    if not math.isfinite(value):
        return ShareResult(
            value=None,
            availability="unavailable",
            evidence_note="non_finite_metric:speaking_share",
            speaking_share_basis="unavailable",
            numerator_seconds=num,
            denominator_seconds=denom,
        )
    availability: Availability = "partial" if missing_timing else "available"
    note = (
        f"missing_timing:{missing_timing}/{len(transcript_contributions)}"
        if missing_timing
        else None
    )
    return ShareResult(
        value=value,
        availability=availability,
        evidence_note=note,
        speaking_share_basis="duration",
        numerator_seconds=num,
        denominator_seconds=denom,
    )


def _finite_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value):
        return None
    return float(value)


def _bucket_rows(
    rows: Sequence[AppearanceRow], grain: AnalyticsGrain
) -> list[tuple[date, str, str, list[AppearanceRow]]]:
    buckets: dict[tuple[date, str, str], list[AppearanceRow]] = {}
    for row in rows:
        sort_key, period_id, label = period_identity(row.appearance_date, grain)
        buckets.setdefault((sort_key, period_id, label), []).append(row)
    return [
        (sk, pid, lab, buckets[(sk, pid, lab)])
        for sk, pid, lab in sorted(buckets.keys(), key=lambda k: (k[0], k[1]))
    ]


def _collect_turn_durations(
    contributions: Sequence[TranscriptContribution],
    bundles: Mapping[str, TranscriptBundle],
) -> tuple[list[float], list[str]]:
    """Indexed by contribution transcript + local keys — never scan all bundles."""
    durations: list[float] = []
    warnings: list[str] = []
    for c in contributions:
        bundle = bundles.get(c.managed_transcript_id)
        if bundle is None:
            warnings.append(f"missing_bundle:{c.managed_transcript_id}")
            continue
        keys = set(c.local_speaker_keys)
        for segment in bundle.segments:
            key = normalize_diarized_id(segment.get("speaker"))
            if key not in keys:
                continue
            d = finite_valid_duration(segment)
            if d is not None:
                durations.append(d)
    return durations, warnings


def _coverage(rows: Sequence[AppearanceRow], *, include_ignored: bool) -> TrendCoverage:
    uncertain = {"needs_review", "missing_source", "collision", "repair_required"}
    return TrendCoverage(
        appearance_count=len(rows),
        excluded_uncertain_count=sum(1 for r in rows if r.flag in uncertain),
        ignored_excluded_count=sum(
            1
            for r in rows
            if (r.ignored or r.flag == "ignored") and not include_ignored
        ),
        untimed_count=sum(1 for r in rows if r.metrics.duration_seconds is None),
    )


def build_trend_bundle(
    appearances: Sequence[AppearanceRow],
    *,
    grain: AnalyticsGrain,
    inclusion: InclusionKind,
    include_ignored: bool,
    transcript_denominators: Mapping[str, float],
    bundles: Mapping[str, TranscriptBundle],
) -> TrendBundle:
    if inclusion == "headline":
        rows = [
            r
            for r in appearances
            if series_eligible(r, include_ignored=include_ignored)
        ]
    else:
        rows = list(appearances)

    speaking_minutes: list[SeriesPoint] = []
    speaking_share: list[SeriesPoint] = []
    words_pts: list[SeriesPoint] = []
    turns_pts: list[SeriesPoint] = []
    avg_pts: list[SeriesPoint] = []
    med_pts: list[SeriesPoint] = []
    wpm_pts: list[SeriesPoint] = []
    integrity_notes: list[str] = []

    for sort_key, period_id, label, group in _bucket_rows(rows, grain):
        contribs = dedupe_to_transcript_contributions(group)
        ids = tuple(sorted({aid for c in contribs for aid in c.source_appearance_ids}))
        tids = tuple(c.managed_transcript_id for c in contribs)

        # Words / turns — always available (may be zero)
        words_total = sum(c.words for c in contribs)
        turns_total = sum(c.turns for c in contribs)
        words_pts.append(
            SeriesPoint(
                metric="words",
                grain=grain,
                period_id=period_id,
                sort_key=sort_key,
                display_label=label,
                value=float(words_total),
                availability="available",
                evidence_note=None,
                source_appearance_ids=ids,
                managed_transcript_ids=tids,
            )
        )
        turns_pts.append(
            SeriesPoint(
                metric="turns",
                grain=grain,
                period_id=period_id,
                sort_key=sort_key,
                display_label=label,
                value=float(turns_total),
                availability="available",
                evidence_note=None,
                source_appearance_ids=ids,
                managed_transcript_ids=tids,
            )
        )

        # Speaking minutes
        timed = [
            c.duration_seconds
            for c in contribs
            if c.duration_seconds is not None and math.isfinite(c.duration_seconds)
        ]
        missing = sum(1 for c in contribs if c.duration_seconds is None)
        if timed:
            minutes = float(sum(timed)) / 60.0
            minutes = _finite_or_none(minutes)
            avail: Availability = "partial" if missing else "available"
            note = f"missing_timing:{missing}/{len(contribs)}" if missing else None
            if minutes is None:
                avail = "unavailable"
                note = "non_finite_metric:speaking_minutes"
            speaking_minutes.append(
                SeriesPoint(
                    metric="speaking_minutes",
                    grain=grain,
                    period_id=period_id,
                    sort_key=sort_key,
                    display_label=label,
                    value=minutes,
                    availability=avail if minutes is not None else "unavailable",
                    evidence_note=note,
                    source_appearance_ids=ids,
                    managed_transcript_ids=tids,
                )
            )
        else:
            speaking_minutes.append(
                SeriesPoint(
                    metric="speaking_minutes",
                    grain=grain,
                    period_id=period_id,
                    sort_key=sort_key,
                    display_label=label,
                    value=None,
                    availability="unavailable",
                    evidence_note=f"missing_timing:{len(contribs)}/{len(contribs)}",
                    source_appearance_ids=ids,
                    managed_transcript_ids=tids,
                )
            )

        share = compute_period_speaking_share(contribs, transcript_denominators)
        speaking_share.append(
            SeriesPoint(
                metric="speaking_share",
                grain=grain,
                period_id=period_id,
                sort_key=sort_key,
                display_label=label,
                value=share.value,
                availability=share.availability,
                evidence_note=share.evidence_note,
                source_appearance_ids=ids,
                managed_transcript_ids=tids,
            )
        )

        # Turn length
        turn_durs, warn = _collect_turn_durations(contribs, bundles)
        integrity_notes.extend(warn)
        n_valid = len(turn_durs)
        if n_valid == 0:
            avg_pts.append(
                SeriesPoint(
                    metric="turn_length_avg",
                    grain=grain,
                    period_id=period_id,
                    sort_key=sort_key,
                    display_label=label,
                    value=None,
                    availability="unavailable",
                    evidence_note="no_timing_valid_turns",
                    source_appearance_ids=ids,
                    managed_transcript_ids=tids,
                    n_valid_turns=0,
                )
            )
            med_pts.append(
                SeriesPoint(
                    metric="turn_length_median",
                    grain=grain,
                    period_id=period_id,
                    sort_key=sort_key,
                    display_label=label,
                    value=None,
                    availability="unavailable",
                    evidence_note="no_timing_valid_turns",
                    source_appearance_ids=ids,
                    managed_transcript_ids=tids,
                    n_valid_turns=0,
                )
            )
        else:
            avg = _finite_or_none(float(sum(turn_durs)) / n_valid)
            med = _finite_or_none(float(statistics.median(turn_durs)))
            partial = any(c.untimed for c in contribs)
            avail_tl: Availability = "partial" if partial else "available"
            note_tl = (
                f"missing_timing:{sum(1 for c in contribs if c.untimed)}/{len(contribs)}"
                if partial
                else None
            )
            avg_pts.append(
                SeriesPoint(
                    metric="turn_length_avg",
                    grain=grain,
                    period_id=period_id,
                    sort_key=sort_key,
                    display_label=label,
                    value=avg,
                    availability=avail_tl if avg is not None else "unavailable",
                    evidence_note=(
                        note_tl
                        if avg is not None
                        else "non_finite_metric:turn_length_avg"
                    ),
                    source_appearance_ids=ids,
                    managed_transcript_ids=tids,
                    n_valid_turns=n_valid,
                )
            )
            med_pts.append(
                SeriesPoint(
                    metric="turn_length_median",
                    grain=grain,
                    period_id=period_id,
                    sort_key=sort_key,
                    display_label=label,
                    value=med,
                    availability=avail_tl if med is not None else "unavailable",
                    evidence_note=(
                        note_tl
                        if med is not None
                        else "non_finite_metric:turn_length_median"
                    ),
                    source_appearance_ids=ids,
                    managed_transcript_ids=tids,
                    n_valid_turns=n_valid,
                )
            )

        # WPM weighted
        wpm_words = 0
        wpm_dur = 0.0
        wpm_missing = 0
        for c in contribs:
            if (
                c.duration_seconds is not None
                and math.isfinite(c.duration_seconds)
                and c.duration_seconds > 0
            ):
                wpm_words += c.words
                wpm_dur += c.duration_seconds
            else:
                wpm_missing += 1
        if wpm_dur > 0:
            wpm = _finite_or_none(wpm_words / (wpm_dur / 60.0))
            avail_w: Availability = "partial" if wpm_missing else "available"
            note_w = (
                f"missing_timing:{wpm_missing}/{len(contribs)}" if wpm_missing else None
            )
            wpm_pts.append(
                SeriesPoint(
                    metric="speaking_rate_wpm",
                    grain=grain,
                    period_id=period_id,
                    sort_key=sort_key,
                    display_label=label,
                    value=wpm,
                    availability=avail_w if wpm is not None else "unavailable",
                    evidence_note=(
                        note_w if wpm is not None else "non_finite_metric:wpm"
                    ),
                    source_appearance_ids=ids,
                    managed_transcript_ids=tids,
                )
            )
        else:
            wpm_pts.append(
                SeriesPoint(
                    metric="speaking_rate_wpm",
                    grain=grain,
                    period_id=period_id,
                    sort_key=sort_key,
                    display_label=label,
                    value=None,
                    availability="unavailable",
                    evidence_note=f"missing_timing:{len(contribs)}/{len(contribs)}",
                    source_appearance_ids=ids,
                    managed_transcript_ids=tids,
                )
            )

    methodology = (
        "share.duration_only",
        "wpm.weighted_period",
        "turn_length.timing_valid_only",
        "partial.available_while_reporting_missing",
        f"grain.{grain}",
    )
    return TrendBundle(
        inclusion=inclusion,
        grain=grain,
        speaking_minutes=tuple(speaking_minutes),
        speaking_share=tuple(speaking_share),
        words=tuple(words_pts),
        turns=tuple(turns_pts),
        turn_length_avg=tuple(avg_pts),
        turn_length_median=tuple(med_pts),
        speaking_rate_wpm=tuple(wpm_pts),
        coverage=_coverage(appearances, include_ignored=include_ignored),
        methodology_codes=methodology,
        integrity_warnings=tuple(sorted(set(integrity_notes))),
    )
