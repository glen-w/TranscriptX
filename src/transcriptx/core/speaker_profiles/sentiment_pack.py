"""Profile sentiment metrics aggregated across linked appearances."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

from transcriptx.core.speaker_profiles.aggregates import series_eligible
from transcriptx.core.speaker_profiles.errors import (
    ProfileAnalyticsMergedError,
    ProfileAnalyticsNotFoundError,
)
from transcriptx.core.speaker_profiles.run_artifact_join import (
    appearance_transcript_path,
    load_json,
    match_keys_for_appearance,
    newest_run_with,
    pick_speaker_entry,
    slug_for_transcript_path,
)
from transcriptx.core.speaker_profiles.snapshot import AggregationSnapshot
from transcriptx.core.utils.paths import OUTPUTS_DIR

__all__ = [
    "ProfileSentimentAppearance",
    "ProfileSentimentPack",
    "build_profile_sentiment_pack",
    "find_sentiment_rows_path",
    "find_sentiment_summary_path",
]

# Same polarity buckets as sentiment module speaker analysis.
_POS_THRESHOLD = 0.05
_NEG_THRESHOLD = -0.05


@dataclass(frozen=True)
class ProfileSentimentAppearance:
    managed_transcript_id: str
    transcript_label: str
    appearance_date: date | None
    session_slug: str
    run_id: str
    matched_speaker: str
    segment_count: int
    compound_mean: float | None
    pos_mean: float | None
    neu_mean: float | None
    neg_mean: float | None
    positive_count: int
    neutral_count: int
    negative_count: int


@dataclass(frozen=True)
class ProfileSentimentPack:
    profile_id: str
    freshness_token: str
    include_ignored: bool
    appearances: tuple[ProfileSentimentAppearance, ...]
    appearances_without_sentiment: int
    segment_count: int
    compound_mean: float | None
    pos_mean: float | None
    neu_mean: float | None
    neg_mean: float | None
    positive_share: float | None
    neutral_share: float | None
    negative_share: float | None
    status: str  # "ok" | "empty"


def _is_segment_rows_name(name: str) -> bool:
    if not name.endswith("_sentiment.json"):
        return False
    if name.endswith("_with_sentiment.json"):
        return False
    if name.endswith("_sentiment_summary.json"):
        return False
    return True


def find_sentiment_rows_path(run_root: Path) -> Path | None:
    """Locate segment-level sentiment JSON (list of speaker/compound/pos/neu/neg)."""
    sentiment_dir = run_root / "sentiment"
    if not sentiment_dir.is_dir():
        return None
    global_dir = sentiment_dir / "data" / "global"
    if global_dir.is_dir():
        matches = sorted(
            p
            for p in global_dir.glob("*_sentiment.json")
            if _is_segment_rows_name(p.name)
        )
        if matches:
            return matches[-1]
    nested = sorted(
        p
        for p in sentiment_dir.rglob("*_sentiment.json")
        if _is_segment_rows_name(p.name)
    )
    return nested[0] if nested else None


def find_sentiment_summary_path(run_root: Path) -> Path | None:
    """Locate sentiment summary JSON with speaker_results."""
    sentiment_dir = run_root / "sentiment"
    if not sentiment_dir.is_dir():
        return None
    global_dir = sentiment_dir / "data" / "global"
    if global_dir.is_dir():
        matches = sorted(global_dir.glob("*_sentiment_summary.json"))
        if matches:
            return matches[-1]
    nested = sorted(sentiment_dir.rglob("*_sentiment_summary.json"))
    return nested[0] if nested else None


def _as_finite_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _metrics_from_rows(
    rows: Sequence[Mapping[str, Any]], match_keys: frozenset[str]
) -> ProfileSentimentAppearance | None:
    compounds: list[float] = []
    pos_vals: list[float] = []
    neu_vals: list[float] = []
    neg_vals: list[float] = []
    matched_speaker = ""
    positive = neutral = negative = 0

    for row in rows:
        if not isinstance(row, Mapping):
            continue
        speaker = str(row.get("speaker") or "").strip()
        if not speaker or speaker.casefold() not in match_keys:
            continue
        if not matched_speaker:
            matched_speaker = speaker
        compound = _as_finite_float(row.get("compound"))
        if compound is None:
            continue
        compounds.append(compound)
        if compound > _POS_THRESHOLD:
            positive += 1
        elif compound < _NEG_THRESHOLD:
            negative += 1
        else:
            neutral += 1
        pos = _as_finite_float(row.get("pos"))
        neu = _as_finite_float(row.get("neu"))
        neg = _as_finite_float(row.get("neg"))
        if pos is not None:
            pos_vals.append(pos)
        if neu is not None:
            neu_vals.append(neu)
        if neg is not None:
            neg_vals.append(neg)

    if not compounds:
        return None

    return ProfileSentimentAppearance(
        managed_transcript_id="",
        transcript_label="",
        appearance_date=None,
        session_slug="",
        run_id="",
        matched_speaker=matched_speaker,
        segment_count=len(compounds),
        compound_mean=_mean(compounds),
        pos_mean=_mean(pos_vals),
        neu_mean=_mean(neu_vals),
        neg_mean=_mean(neg_vals),
        positive_count=positive,
        neutral_count=neutral,
        negative_count=negative,
    )


def _metrics_from_summary(
    payload: Mapping[str, Any], match_keys: frozenset[str]
) -> ProfileSentimentAppearance | None:
    speaker_results = payload.get("speaker_results")
    if not isinstance(speaker_results, Mapping):
        return None
    picked = pick_speaker_entry(speaker_results, match_keys)
    if picked is None:
        return None
    speaker, entry = picked
    if not isinstance(entry, Mapping):
        return None
    compound = _as_finite_float(entry.get("compound_mean"))
    if compound is None:
        return None
    count = entry.get("count")
    try:
        segment_count = max(0, int(count)) if count is not None else 0
    except (TypeError, ValueError):
        segment_count = 0

    pos = _as_finite_float(entry.get("pos_mean"))
    neu = _as_finite_float(entry.get("neu_mean"))
    neg = _as_finite_float(entry.get("neg_mean"))
    # Historical summaries stub pos/neu/neg as 0; treat as unavailable when
    # all three are exactly 0 while compound is non-zero.
    if (
        pos == 0.0
        and neu == 0.0
        and neg == 0.0
        and compound is not None
        and compound != 0.0
    ):
        pos = neu = neg = None

    return ProfileSentimentAppearance(
        managed_transcript_id="",
        transcript_label="",
        appearance_date=None,
        session_slug="",
        run_id="",
        matched_speaker=speaker,
        segment_count=segment_count,
        compound_mean=compound,
        pos_mean=pos,
        neu_mean=neu,
        neg_mean=neg,
        positive_count=0,
        neutral_count=0,
        negative_count=0,
    )


def _find_sentiment_artifact(run_root: Path) -> Path | None:
    """Prefer segment rows; fall back to summary."""
    rows = find_sentiment_rows_path(run_root)
    if rows is not None:
        return rows
    return find_sentiment_summary_path(run_root)


def _weighted_mean(
    pairs: Sequence[tuple[float, int]],
) -> float | None:
    total_w = sum(w for _v, w in pairs if w > 0)
    if total_w <= 0:
        # Fall back to unweighted mean of values
        vals = [v for v, _w in pairs]
        return _mean(vals)
    return sum(v * w for v, w in pairs if w > 0) / total_w


def build_profile_sentiment_pack(
    snap: AggregationSnapshot,
    profile_id: str,
    *,
    include_ignored: bool = False,
    outputs_dir: Path | None = None,
) -> ProfileSentimentPack:
    """Aggregate sentiment means for a profile across headline appearances."""
    profile = snap.profiles_by_id.get(profile_id)
    profile_model = next((p for p in snap.profiles if p.profile_id == profile_id), None)
    if profile is None or profile_model is None:
        raise ProfileAnalyticsNotFoundError(f"profile not found: {profile_id}")
    if profile.status == "merged":
        raise ProfileAnalyticsMergedError(
            f"profile {profile_id} is merged into {profile.merged_into_profile_id}"
        )

    agg = snap.aggregates_by_profile.get(profile_id)
    freshness = agg.freshness_token if agg is not None else ""
    appearances = snap.appearances_by_profile.get(profile_id, ())
    eligible = [
        row
        for row in appearances
        if series_eligible(row, include_ignored=include_ignored)
    ]

    rows_out: list[ProfileSentimentAppearance] = []
    appearances_without = 0
    out_root = Path(outputs_dir) if outputs_dir is not None else Path(OUTPUTS_DIR)

    for row in eligible:
        path = appearance_transcript_path(snap, row)
        if path is None:
            appearances_without += 1
            continue
        session_slug = slug_for_transcript_path(path)
        if not session_slug:
            appearances_without += 1
            continue

        found = newest_run_with(
            session_slug,
            _find_sentiment_artifact,
            outputs_dir=out_root,
        )
        if found is None:
            appearances_without += 1
            continue
        run_id, artifact_path = found
        payload = load_json(artifact_path)
        if payload is None:
            appearances_without += 1
            continue

        match_keys = match_keys_for_appearance(
            profile=profile_model,
            local_speaker_key=row.local_speaker_key,
            transcript_path=path,
        )

        metrics: ProfileSentimentAppearance | None = None
        if isinstance(payload, list):
            metrics = _metrics_from_rows(payload, match_keys)
        elif isinstance(payload, dict):
            # Segment rows accidentally wrapped, or summary
            if "speaker_results" in payload:
                metrics = _metrics_from_summary(payload, match_keys)
            else:
                appearances_without += 1
                continue
        else:
            appearances_without += 1
            continue

        if metrics is None:
            appearances_without += 1
            continue

        rows_out.append(
            ProfileSentimentAppearance(
                managed_transcript_id=row.managed_transcript_id,
                transcript_label=row.current_relpath or row.observed_transcript_relpath,
                appearance_date=row.appearance_date,
                session_slug=session_slug,
                run_id=run_id,
                matched_speaker=metrics.matched_speaker,
                segment_count=metrics.segment_count,
                compound_mean=metrics.compound_mean,
                pos_mean=metrics.pos_mean,
                neu_mean=metrics.neu_mean,
                neg_mean=metrics.neg_mean,
                positive_count=metrics.positive_count,
                neutral_count=metrics.neutral_count,
                negative_count=metrics.negative_count,
            )
        )

    compound_pairs = [
        (r.compound_mean, r.segment_count)
        for r in rows_out
        if r.compound_mean is not None
    ]
    pos_pairs = [
        (r.pos_mean, r.segment_count) for r in rows_out if r.pos_mean is not None
    ]
    neu_pairs = [
        (r.neu_mean, r.segment_count) for r in rows_out if r.neu_mean is not None
    ]
    neg_pairs = [
        (r.neg_mean, r.segment_count) for r in rows_out if r.neg_mean is not None
    ]

    total_segments = sum(r.segment_count for r in rows_out)
    pos_n = sum(r.positive_count for r in rows_out)
    neu_n = sum(r.neutral_count for r in rows_out)
    neg_n = sum(r.negative_count for r in rows_out)
    polarity_n = pos_n + neu_n + neg_n

    return ProfileSentimentPack(
        profile_id=profile_id,
        freshness_token=freshness,
        include_ignored=include_ignored,
        appearances=tuple(rows_out),
        appearances_without_sentiment=appearances_without,
        segment_count=total_segments,
        compound_mean=_weighted_mean(compound_pairs),
        pos_mean=_weighted_mean(pos_pairs),
        neu_mean=_weighted_mean(neu_pairs),
        neg_mean=_weighted_mean(neg_pairs),
        positive_share=(pos_n / polarity_n) if polarity_n else None,
        neutral_share=(neu_n / polarity_n) if polarity_n else None,
        negative_share=(neg_n / polarity_n) if polarity_n else None,
        status="ok" if rows_out else "empty",
    )
