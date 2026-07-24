"""Profile interactions / equity metrics aggregated across linked appearances."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping

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
    "ProfileInteractionAppearance",
    "ProfileInteractionsPack",
    "build_profile_interactions_pack",
    "find_interactions_speaker_summary_path",
]


@dataclass(frozen=True)
class ProfileInteractionAppearance:
    managed_transcript_id: str
    transcript_label: str
    appearance_date: date | None
    session_slug: str
    run_id: str
    matched_speaker: str
    interruptions_initiated: int
    interruptions_received: int
    responses_initiated: int
    responses_received: int
    net_interruption_balance: int
    net_response_balance: int
    total_interactions: int
    dominance_score: float | None
    floor_share: float | None
    interruption_asymmetry: float | None
    response_latency_mean: float | None


@dataclass(frozen=True)
class ProfileInteractionsPack:
    profile_id: str
    freshness_token: str
    include_ignored: bool
    appearances: tuple[ProfileInteractionAppearance, ...]
    appearances_without_interactions: int
    total_interruptions_initiated: int
    total_interruptions_received: int
    total_responses_initiated: int
    total_responses_received: int
    mean_dominance_score: float | None
    mean_floor_share: float | None
    status: str  # "ok" | "empty"


def find_interactions_speaker_summary_path(run_root: Path) -> Path | None:
    """Locate interactions speaker_summary JSON under a run root."""
    interactions_dir = run_root / "interactions"
    if not interactions_dir.is_dir():
        return None
    global_dir = interactions_dir / "data" / "global"
    if global_dir.is_dir():
        matches = sorted(global_dir.glob("*_speaker_summary.json"))
        if matches:
            return matches[-1]
    direct = interactions_dir / "speaker_summary.json"
    if direct.is_file():
        return direct
    nested = sorted(interactions_dir.rglob("*_speaker_summary.json"))
    return nested[0] if nested else None


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


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


def _lookup_count(mapping: Mapping[str, Any], speaker: str) -> int:
    if speaker in mapping:
        return _as_int(mapping.get(speaker), 0)
    folded = speaker.casefold()
    for key, value in mapping.items():
        if str(key).casefold() == folded:
            return _as_int(value, 0)
    return 0


def _extract_speaker_metrics(
    payload: Mapping[str, Any], match_keys: frozenset[str]
) -> ProfileInteractionAppearance | None:
    """Build metrics for the first speaker key matching ``match_keys``."""
    initiated = payload.get("interruption_initiated")
    if not isinstance(initiated, Mapping):
        initiated = {}
    picked = pick_speaker_entry(initiated, match_keys)
    # Also try other count maps if interruption map had no match
    if picked is None:
        for field in (
            "responses_initiated",
            "interruption_received",
            "responses_received",
            "total_interactions",
            "dominance_scores",
        ):
            mapping = payload.get(field)
            if isinstance(mapping, Mapping):
                picked = pick_speaker_entry(mapping, match_keys)
                if picked is not None:
                    break
    equity = payload.get("equity")
    if not isinstance(equity, Mapping):
        equity = {}
    if picked is None:
        floor_share_map = equity.get("floor_share")
        if isinstance(floor_share_map, Mapping):
            picked = pick_speaker_entry(floor_share_map, match_keys)
    if picked is None:
        return None

    speaker, _ = picked
    responses_initiated = payload.get("responses_initiated")
    interruption_received = payload.get("interruption_received")
    responses_received = payload.get("responses_received")
    net_interruption = payload.get("net_interruption_balance")
    net_response = payload.get("net_response_balance")
    totals = payload.get("total_interactions")
    dominance = payload.get("dominance_scores")

    floor_share = None
    floor_map = equity.get("floor_share")
    if isinstance(floor_map, Mapping):
        floor_share = _as_finite_float(
            floor_map.get(speaker)
            if speaker in floor_map
            else next(
                (
                    floor_map[k]
                    for k in floor_map
                    if str(k).casefold() == speaker.casefold()
                ),
                None,
            )
        )

    asymmetry = None
    asym_map = equity.get("interruption_asymmetry")
    if isinstance(asym_map, Mapping):
        asymmetry = _as_finite_float(
            asym_map.get(speaker)
            if speaker in asym_map
            else next(
                (
                    asym_map[k]
                    for k in asym_map
                    if str(k).casefold() == speaker.casefold()
                ),
                None,
            )
        )

    latency_mean = None
    latency_map = equity.get("response_latency")
    if isinstance(latency_map, Mapping):
        latency_entry = latency_map.get(speaker)
        if latency_entry is None:
            for key, value in latency_map.items():
                if str(key).casefold() == speaker.casefold():
                    latency_entry = value
                    break
        if isinstance(latency_entry, Mapping):
            latency_mean = _as_finite_float(latency_entry.get("mean"))

    dominance_score = None
    if isinstance(dominance, Mapping):
        dominance_score = _as_finite_float(
            dominance.get(speaker)
            if speaker in dominance
            else next(
                (
                    dominance[k]
                    for k in dominance
                    if str(k).casefold() == speaker.casefold()
                ),
                None,
            )
        )

    return ProfileInteractionAppearance(
        managed_transcript_id="",  # filled by caller
        transcript_label="",
        appearance_date=None,
        session_slug="",
        run_id="",
        matched_speaker=speaker,
        interruptions_initiated=_lookup_count(
            initiated if isinstance(initiated, Mapping) else {}, speaker
        ),
        interruptions_received=_lookup_count(
            interruption_received if isinstance(interruption_received, Mapping) else {},
            speaker,
        ),
        responses_initiated=_lookup_count(
            responses_initiated if isinstance(responses_initiated, Mapping) else {},
            speaker,
        ),
        responses_received=_lookup_count(
            responses_received if isinstance(responses_received, Mapping) else {},
            speaker,
        ),
        net_interruption_balance=_lookup_count(
            net_interruption if isinstance(net_interruption, Mapping) else {}, speaker
        ),
        net_response_balance=_lookup_count(
            net_response if isinstance(net_response, Mapping) else {}, speaker
        ),
        total_interactions=_lookup_count(
            totals if isinstance(totals, Mapping) else {}, speaker
        ),
        dominance_score=dominance_score,
        floor_share=floor_share,
        interruption_asymmetry=asymmetry,
        response_latency_mean=latency_mean,
    )


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def build_profile_interactions_pack(
    snap: AggregationSnapshot,
    profile_id: str,
    *,
    include_ignored: bool = False,
    outputs_dir: Path | None = None,
) -> ProfileInteractionsPack:
    """Aggregate interactions / equity metrics for a profile across appearances."""
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

    rows: list[ProfileInteractionAppearance] = []
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
            find_interactions_speaker_summary_path,
            outputs_dir=out_root,
        )
        if found is None:
            appearances_without += 1
            continue
        run_id, summary_path = found
        payload = load_json(summary_path)
        if not isinstance(payload, dict):
            appearances_without += 1
            continue

        match_keys = match_keys_for_appearance(
            profile=profile_model,
            local_speaker_key=row.local_speaker_key,
            transcript_path=path,
        )
        metrics = _extract_speaker_metrics(payload, match_keys)
        if metrics is None:
            appearances_without += 1
            continue

        rows.append(
            ProfileInteractionAppearance(
                managed_transcript_id=row.managed_transcript_id,
                transcript_label=row.current_relpath or row.observed_transcript_relpath,
                appearance_date=row.appearance_date,
                session_slug=session_slug,
                run_id=run_id,
                matched_speaker=metrics.matched_speaker,
                interruptions_initiated=metrics.interruptions_initiated,
                interruptions_received=metrics.interruptions_received,
                responses_initiated=metrics.responses_initiated,
                responses_received=metrics.responses_received,
                net_interruption_balance=metrics.net_interruption_balance,
                net_response_balance=metrics.net_response_balance,
                total_interactions=metrics.total_interactions,
                dominance_score=metrics.dominance_score,
                floor_share=metrics.floor_share,
                interruption_asymmetry=metrics.interruption_asymmetry,
                response_latency_mean=metrics.response_latency_mean,
            )
        )

    dominance_vals = [r.dominance_score for r in rows if r.dominance_score is not None]
    floor_vals = [r.floor_share for r in rows if r.floor_share is not None]

    return ProfileInteractionsPack(
        profile_id=profile_id,
        freshness_token=freshness,
        include_ignored=include_ignored,
        appearances=tuple(rows),
        appearances_without_interactions=appearances_without,
        total_interruptions_initiated=sum(r.interruptions_initiated for r in rows),
        total_interruptions_received=sum(r.interruptions_received for r in rows),
        total_responses_initiated=sum(r.responses_initiated for r in rows),
        total_responses_received=sum(r.responses_received for r in rows),
        mean_dominance_score=_mean(dominance_vals),
        mean_floor_share=_mean(floor_vals),
        status="ok" if rows else "empty",
    )
