"""Profile analytics pack facade — six longitudinal views from one snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from transcriptx.core.speaker_profiles.errors import (
    ProfileAnalyticsMergedError,
    ProfileAnalyticsNotFoundError,
)
from transcriptx.core.speaker_profiles.longitudinal import (
    AnalyticsGrain,
    TrendBundle,
    build_trend_bundle,
)
from transcriptx.core.speaker_profiles.partners import (
    PartnerAggregationResult,
    PartnerSummary,
    build_conversation_partners,
)
from transcriptx.core.speaker_profiles.snapshot import AggregationSnapshot

PARTNERS_TOP_N = 10

# Re-export for callers
__all__ = [
    "PARTNERS_TOP_N",
    "ProfileAnalyticsMergedError",
    "ProfileAnalyticsNotFoundError",
    "ProfileAnalyticsPack",
    "build_profile_analytics_pack",
]


@dataclass(frozen=True)
class ProfileAnalyticsPack:
    profile_id: str
    freshness_token: str
    grain: AnalyticsGrain
    include_ignored: bool
    include_all_series: bool
    headline: TrendBundle
    all_appearances: TrendBundle | None
    partners: tuple[PartnerSummary, ...]
    partners_remainder_count: int
    integrity_warnings: tuple[str, ...]
    methodology_codes: tuple[str, ...]
    status: Literal["ok", "empty"]


def build_profile_analytics_pack(
    snap: AggregationSnapshot,
    profile_id: str,
    *,
    grain: AnalyticsGrain = "appearance_date",
    include_ignored: bool = False,
    include_all_series: bool = False,
) -> ProfileAnalyticsPack:
    """Pure transform over AggregationSnapshot — no filesystem or resolver calls."""
    pref = snap.profiles_by_id.get(profile_id)
    if pref is None:
        raise ProfileAnalyticsNotFoundError(f"profile not found: {profile_id}")
    if pref.status == "merged":
        raise ProfileAnalyticsMergedError(
            f"profile {profile_id} is merged into {pref.merged_into_profile_id}"
        )

    agg = snap.aggregates_by_profile.get(profile_id)
    appearances = snap.appearances_by_profile.get(profile_id, ())
    freshness = agg.freshness_token if agg is not None else ""

    headline = build_trend_bundle(
        appearances,
        grain=grain,
        inclusion="headline",
        include_ignored=include_ignored,
        transcript_denominators=snap.transcript_denominators,
        bundles=snap.bundles,
    )
    all_bundle = None
    if include_all_series:
        all_bundle = build_trend_bundle(
            appearances,
            grain=grain,
            inclusion="all",
            include_ignored=include_ignored,
            transcript_denominators=snap.transcript_denominators,
            bundles=snap.bundles,
        )

    partner_result: PartnerAggregationResult = build_conversation_partners(
        subject_profile_id=profile_id,
        subject_appearances=appearances,
        links=snap.links,
        profiles_by_id=snap.profiles_by_id,
        include_ignored=include_ignored,
        top_n=PARTNERS_TOP_N,
    )

    methodology = tuple(
        sorted(
            set(headline.methodology_codes)
            | {"partners.co_appearance_only", "pack.phase16"}
        )
    )
    warnings = tuple(
        sorted(
            set(headline.integrity_warnings)
            | set(all_bundle.integrity_warnings if all_bundle is not None else ())
            | set(partner_result.integrity_warnings)
        )
    )
    status: Literal["ok", "empty"] = "empty" if not appearances else "ok"
    return ProfileAnalyticsPack(
        profile_id=profile_id,
        freshness_token=freshness,
        grain=grain,
        include_ignored=include_ignored,
        include_all_series=include_all_series,
        headline=headline,
        all_appearances=all_bundle,
        partners=partner_result.partners,
        partners_remainder_count=partner_result.remainder_count,
        integrity_warnings=warnings,
        methodology_codes=methodology,
        status=status,
    )
