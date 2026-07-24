"""Conversation partner (co-appearance) aggregation for profile analytics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

from transcriptx.core.speaker_profiles.aggregates import AppearanceRow, series_eligible
from transcriptx.core.speaker_profiles.longitudinal import Availability
from transcriptx.core.speaker_profiles.models import SpeakerProfileLinkV1
from transcriptx.core.speaker_profiles.snapshot import ProfileRef

PartnerStatus = Literal["active", "archived"]


@dataclass(frozen=True)
class PartnerSummary:
    partner_id: str
    display_name: str
    status: PartnerStatus
    shared_transcript_count: int
    shared_speaking_minutes: float | None
    availability: Availability
    evidence_note: str | None
    shared_managed_transcript_ids: tuple[str, ...]


@dataclass(frozen=True)
class PartnerAggregationResult:
    partners: tuple[PartnerSummary, ...]
    remainder_count: int
    integrity_warnings: tuple[str, ...]


_TOP_N = 10


def build_conversation_partners(
    *,
    subject_profile_id: str,
    subject_appearances: Sequence[AppearanceRow],
    links: Sequence[SpeakerProfileLinkV1],
    profiles_by_id: Mapping[str, ProfileRef],
    include_ignored: bool = False,
    top_n: int = _TOP_N,
) -> PartnerAggregationResult:
    """Rank co-appearance partners from snapshot data only (no FS/resolver)."""
    warnings: list[str] = []
    eligible_subject = [
        r
        for r in subject_appearances
        if series_eligible(r, include_ignored=include_ignored)
    ]
    from transcriptx.core.speaker_profiles.longitudinal import (
        dedupe_to_transcript_contributions,
    )

    # Subject minutes per transcript after numerator dedupe
    subject_minutes_by_tid: dict[str, float | None] = {}
    for c in dedupe_to_transcript_contributions(eligible_subject):
        dur = c.duration_seconds
        if dur is not None and not math.isfinite(dur):
            warnings.append(
                f"non_finite_metric:partner_subject_duration:{c.managed_transcript_id}"
            )
            subject_minutes_by_tid[c.managed_transcript_id] = None
        else:
            subject_minutes_by_tid[c.managed_transcript_id] = dur

    # Index links by transcript; keep first link_id per (tid, profile_id)
    links_by_tid: dict[str, list[SpeakerProfileLinkV1]] = {}
    for link in sorted(links, key=lambda ln: ln.link_id):
        links_by_tid.setdefault(link.managed_transcript_id, []).append(link)

    # partner_id -> tid -> subject duration seconds
    shared: dict[str, dict[str, float | None]] = {}
    seen_partner_link: set[tuple[str, str]] = set()  # (tid, partner_id)

    for tid, subject_dur in subject_minutes_by_tid.items():
        for link in links_by_tid.get(tid, ()):
            if link.profile_id == subject_profile_id:
                continue
            edge = (tid, link.profile_id)
            if edge in seen_partner_link:
                warnings.append(f"duplicate_live_link:{tid}:{link.profile_id}")
                continue
            seen_partner_link.add(edge)

            pref = profiles_by_id.get(link.profile_id)
            if pref is None:
                warnings.append(f"dangling_partner_profile:{link.profile_id}")
                continue
            if pref.status == "merged":
                warnings.append(f"merged_owner_link:{link.profile_id}")
                continue
            if pref.status not in {"active", "archived"}:
                warnings.append(
                    f"unknown_partner_status:{link.profile_id}:{pref.status}"
                )
                continue
            shared.setdefault(link.profile_id, {})[tid] = subject_dur

    partners: list[PartnerSummary] = []
    for partner_id, tid_map in shared.items():
        pref = profiles_by_id[partner_id]
        tids = tuple(sorted(tid_map.keys()))
        timed = [v for v in tid_map.values() if v is not None]
        missing = sum(1 for v in tid_map.values() if v is None)
        if timed:
            minutes = float(sum(timed)) / 60.0
            if not math.isfinite(minutes):
                minutes = None
                avail: Availability = "unavailable"
                note = "non_finite_metric:partner_minutes"
            else:
                avail = "partial" if missing else "available"
                note = f"missing_timing:{missing}/{len(tid_map)}" if missing else None
        else:
            minutes = None
            avail = "unavailable"
            note = f"missing_timing:{len(tid_map)}/{len(tid_map)}"
        partners.append(
            PartnerSummary(
                partner_id=partner_id,
                display_name=pref.display_name,
                status=pref.status,  # type: ignore[arg-type]
                shared_transcript_count=len(tids),
                shared_speaking_minutes=minutes,
                availability=avail,
                evidence_note=note,
                shared_managed_transcript_ids=tids,
            )
        )

    def rank_key(p: PartnerSummary) -> tuple:
        if p.shared_speaking_minutes is None:
            sec = (1, 0.0)
        else:
            sec = (0, -p.shared_speaking_minutes)
        return (
            -p.shared_transcript_count,
            sec[0],
            sec[1],
            p.display_name.lower(),
            p.partner_id,
        )

    ranked = sorted(partners, key=rank_key)
    top = ranked[:top_n]
    remainder = max(0, len(ranked) - top_n)
    return PartnerAggregationResult(
        partners=tuple(top),
        remainder_count=remainder,
        integrity_warnings=tuple(sorted(set(warnings))),
    )
