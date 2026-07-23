"""Raw-key speaker appearance metrics (not compute_speaker_stats)."""

from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from transcriptx.core.speaker_profiles.dates import appearance_date_from_sources
from transcriptx.core.speaker_profiles.errors import (
    CorruptLinkError,
    RepairRequiredError,
    UnresolvedManagedTranscriptError,
)
from transcriptx.core.speaker_profiles.fingerprint import compute_occurrence_fingerprint
from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.layout import links_dir, profiles_dir
from transcriptx.core.speaker_profiles.models import (
    SpeakerProfileLinkV1,
    SpeakerProfileV1,
)
from transcriptx.core.speaker_profiles.resolver import (
    ManagedTranscriptResolver,
    load_transcript_segments,
)
from transcriptx.core.speaker_profiles.store_io import parse_model
from transcriptx.core.utils.segment_duration import valid_segment_duration
from transcriptx.io.speaker_map_resolver import (
    SpeakerMapResolver,
    normalize_diarized_id,
)

SpeakingShareBasis = Literal["duration", "unavailable"]
AppearanceFlag = Literal[
    "ok",
    "needs_review",
    "missing_source",
    "collision",
    "ignored",
    "repair_required",
]


@dataclass(frozen=True)
class OccurrenceMetrics:
    words: int
    turns: int
    duration_seconds: float | None
    """Sum of valid durations; None if no timing-valid segments contributed duration."""

    avg_turn_duration: float | None
    median_turn_duration: float | None
    wpm: float | None


@dataclass(frozen=True)
class AppearanceRow:
    profile_id: str
    link_id: str
    managed_transcript_id: str
    local_speaker_key: str
    link_file_key: str
    observed_transcript_relpath: str
    current_relpath: str | None
    appearance_date: date | None
    flag: AppearanceFlag
    ignored: bool
    metrics: OccurrenceMetrics
    speaking_share: float | None = None
    speaking_share_basis: SpeakingShareBasis = "unavailable"
    turn_share: float | None = None


@dataclass(frozen=True)
class ProfileAggregate:
    profile_id: str
    display_name: str
    status: str
    merged_into_profile_id: str | None
    headline_words: int
    headline_turns: int
    headline_duration_seconds: float
    headline_speaking_share: float | None
    speaking_share_basis: SpeakingShareBasis
    headline_turn_share: float | None
    appearance_count: int
    headline_appearance_count: int
    pending_review_count: int
    missing_source_count: int
    ignored_linked_count: int
    collision_count: int
    repair_required_count: int
    appearances: tuple[AppearanceRow, ...]
    freshness_token: str


@dataclass(frozen=True)
class ProfileListItem:
    profile_id: str
    display_name: str
    status: str
    merged_into_profile_id: str | None
    updated_at: str
    link_count: int
    needs_repair: bool = False


def compute_occurrence_metrics(
    segments: Sequence[Mapping[str, Any]],
) -> OccurrenceMetrics:
    """Metrics for segments belonging to one local speaker key."""
    words = 0
    turns = 0
    durations: list[float] = []
    for segment in segments:
        turns += 1
        text = segment.get("text")
        if text is not None:
            words += len(str(text).split())
        dur = valid_segment_duration(segment)
        if dur is not None:
            durations.append(float(dur))
    if not durations:
        duration_sum: float | None = None
        avg = None
        med = None
        wpm = None
    else:
        duration_sum = float(sum(durations))
        avg = duration_sum / len(durations)
        med = float(statistics.median(durations))
        minutes = duration_sum / 60.0
        wpm = (words / minutes) if minutes > 0 else None
    return OccurrenceMetrics(
        words=words,
        turns=turns,
        duration_seconds=duration_sum,
        avg_turn_duration=avg,
        median_turn_duration=med,
        wpm=wpm,
    )


def _is_ignored(transcript_path: Path, local_speaker_key: str) -> bool:
    try:
        state = SpeakerMapResolver().load_mapping(str(transcript_path))
    except Exception:
        return False
    ignored = {
        normalize_diarized_id(x)
        for x in (state.ignored_speakers or [])
        if normalize_diarized_id(x)
    }
    return local_speaker_key in ignored


def build_appearance_row(
    *,
    profile: SpeakerProfileV1,
    link: SpeakerProfileLinkV1,
    resolver: ManagedTranscriptResolver,
    include_ignored: bool = False,
) -> AppearanceRow:
    key = link_file_key(link.managed_transcript_id, link.local_speaker_key)
    flag: AppearanceFlag = "ok"
    ignored = False
    current_relpath: str | None = None
    appearance_date: date | None = None
    metrics = OccurrenceMetrics(
        words=0, turns=0, duration_seconds=None,
        avg_turn_duration=None, median_turn_duration=None, wpm=None,
    )
    try:
        resolved = resolver.resolve(link.managed_transcript_id)
        current_relpath = resolved.current_relpath
        appearance_date = appearance_date_from_sources(
            transcript_source_imported_at=resolved.source_imported_at,
            sidecar_imported_at=resolved.sidecar_imported_at,
        )
        segments = load_transcript_segments(resolved.transcript_path)
        keyed = [
            s
            for s in segments
            if normalize_diarized_id(s.get("speaker")) == link.local_speaker_key
        ]
        # Collision among raw forms for this key
        raws = {str(s.get("speaker")).strip() for s in keyed if s.get("speaker")}
        if len(raws) > 1:
            flag = "collision"
        fp = compute_occurrence_fingerprint(keyed)
        if fp != link.occurrence_fingerprint:
            flag = "needs_review"
        ignored = _is_ignored(resolved.transcript_path, link.local_speaker_key)
        if ignored and flag == "ok":
            flag = "ignored"
        metrics = compute_occurrence_metrics(keyed)
    except UnresolvedManagedTranscriptError:
        flag = "missing_source"
    except (RepairRequiredError, CorruptLinkError):
        flag = "repair_required"
    except Exception:
        flag = "missing_source"

    return AppearanceRow(
        profile_id=profile.profile_id,
        link_id=link.link_id,
        managed_transcript_id=link.managed_transcript_id,
        local_speaker_key=link.local_speaker_key,
        link_file_key=key,
        observed_transcript_relpath=link.observed_transcript_relpath,
        current_relpath=current_relpath,
        appearance_date=appearance_date,
        flag=flag,
        ignored=ignored,
        metrics=metrics,
    )


def _headline_eligible(row: AppearanceRow, *, include_ignored: bool) -> bool:
    if row.flag in {"needs_review", "missing_source", "collision", "repair_required"}:
        return False
    if row.ignored and not include_ignored:
        return False
    if row.flag == "ignored" and not include_ignored:
        return False
    return True


def aggregate_profile(
    profile: SpeakerProfileV1,
    links: Sequence[SpeakerProfileLinkV1],
    *,
    resolver: ManagedTranscriptResolver,
    include_ignored: bool = False,
) -> ProfileAggregate:
    rows = [
        build_appearance_row(
            profile=profile, link=link, resolver=resolver, include_ignored=include_ignored
        )
        for link in links
    ]
    headline = [r for r in rows if _headline_eligible(r, include_ignored=include_ignored)]
    total_duration = 0.0
    for r in headline:
        if r.metrics.duration_seconds is not None:
            total_duration += r.metrics.duration_seconds
    # Denominator for speaking_share: sum of headline durations across this profile's
    # appearances only when computing per-appearance shares against profile total.
    # Profile-level speaking_share vs corpus requires corpus denom; here we expose
    # share of each appearance within profile headline duration, and profile-level
    # basis unavailable when total_duration == 0.
    enriched: list[AppearanceRow] = []
    headline_turns = sum(h.metrics.turns for h in headline)
    for r in rows:
        share = None
        basis: SpeakingShareBasis = "unavailable"
        turn_share = None
        if _headline_eligible(r, include_ignored=include_ignored):
            if total_duration > 0 and r.metrics.duration_seconds is not None:
                share = r.metrics.duration_seconds / total_duration
                basis = "duration"
            if headline_turns > 0:
                turn_share = r.metrics.turns / headline_turns
        enriched.append(
            replace(
                r,
                speaking_share=share,
                speaking_share_basis=basis,
                turn_share=turn_share,
            )
        )

    hw = sum(r.metrics.words for r in headline)
    ht = sum(r.metrics.turns for r in headline)
    token_payload = {
        "profile_id": profile.profile_id,
        "updated_at": profile.updated_at,
        "link_ids": sorted(r.link_id for r in enriched),
        "flags": sorted(f"{r.link_id}:{r.flag}" for r in enriched),
        "headline_words": hw,
        "headline_turns": ht,
        "headline_duration": total_duration,
    }
    freshness = hashlib.sha256(
        json.dumps(token_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()

    return ProfileAggregate(
        profile_id=profile.profile_id,
        display_name=profile.display_name,
        status=profile.status,
        merged_into_profile_id=profile.merged_into_profile_id,
        headline_words=hw,
        headline_turns=ht,
        headline_duration_seconds=total_duration,
        headline_speaking_share=None,
        speaking_share_basis="duration" if total_duration > 0 else "unavailable",
        headline_turn_share=None,
        appearance_count=len(enriched),
        headline_appearance_count=len(headline),
        pending_review_count=sum(1 for r in enriched if r.flag == "needs_review"),
        missing_source_count=sum(1 for r in enriched if r.flag == "missing_source"),
        ignored_linked_count=sum(1 for r in enriched if r.ignored or r.flag == "ignored"),
        collision_count=sum(1 for r in enriched if r.flag == "collision"),
        repair_required_count=sum(1 for r in enriched if r.flag == "repair_required"),
        appearances=tuple(enriched),
        freshness_token=freshness,
    )


def list_profile_links(profile_id: str, *, root: Path) -> list[SpeakerProfileLinkV1]:
    links_root = links_dir(root)
    if not links_root.is_dir():
        return []
    out: list[SpeakerProfileLinkV1] = []
    for path in sorted(links_root.glob("*.speaker_link.json")):
        try:
            link = parse_model(SpeakerProfileLinkV1, path)
        except Exception:
            continue
        if link.profile_id == profile_id:
            out.append(link)
    return out


def list_profiles(*, root: Path) -> list[ProfileListItem]:
    from transcriptx.core.speaker_profiles.recovery import blocking_operations_for_path
    from transcriptx.core.speaker_profiles.operations import relative_profile_path

    pref = profiles_dir(root)
    if not pref.is_dir():
        return []
    items: list[ProfileListItem] = []
    for path in sorted(pref.glob("*.speaker_profile.json")):
        try:
            profile = parse_model(SpeakerProfileV1, path)
        except Exception:
            continue
        links = list_profile_links(profile.profile_id, root=root)
        blocked = blocking_operations_for_path(
            root, relative_profile_path(profile.profile_id)
        )
        items.append(
            ProfileListItem(
                profile_id=profile.profile_id,
                display_name=profile.display_name,
                status=profile.status,
                merged_into_profile_id=profile.merged_into_profile_id,
                updated_at=profile.updated_at,
                link_count=len(links),
                needs_repair=bool(blocked),
            )
        )
    return items


def resolve_profile_redirect(
    profile_id: str, *, root: Path, max_hops: int = 16
) -> SpeakerProfileV1:
    """Follow merged_into_profile_id with cycle detection."""
    from transcriptx.core.speaker_profiles.store_io import read_profile

    seen: set[str] = set()
    current_id = profile_id
    for _ in range(max_hops):
        if current_id in seen:
            raise RepairRequiredError(f"merge redirect cycle involving {profile_id}")
        seen.add(current_id)
        profile = read_profile(current_id, root=root)
        if profile is None:
            raise RepairRequiredError(f"profile not found: {current_id}")
        if profile.status != "merged" or not profile.merged_into_profile_id:
            return profile
        current_id = profile.merged_into_profile_id
    raise RepairRequiredError(f"merge redirect exceeded max hops for {profile_id}")
