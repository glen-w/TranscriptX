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
    aliases: tuple[str, ...] = ()
    accent_color: str | None = None
    incomplete: bool = False


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


def _transcript_duration_denominator(
    segments: Sequence[Mapping[str, Any]],
) -> float | None:
    total = 0.0
    any_valid = False
    for segment in segments:
        dur = valid_segment_duration(segment)
        if dur is not None:
            total += float(dur)
            any_valid = True
    return total if any_valid else None


def resolve_appearance_flag(
    *,
    repair_required: bool = False,
    missing_source: bool = False,
    collision: bool = False,
    needs_review: bool = False,
    ignored: bool = False,
) -> AppearanceFlag:
    """Single-winner flag precedence (higher wins)."""
    if repair_required:
        return "repair_required"
    if missing_source:
        return "missing_source"
    if collision:
        return "collision"
    if needs_review:
        return "needs_review"
    if ignored:
        return "ignored"
    return "ok"


def headline_eligible(row: AppearanceRow, *, include_ignored: bool) -> bool:
    """Public predicate shared by aggregates and time-series builders."""
    if row.flag in {"needs_review", "missing_source", "collision", "repair_required"}:
        return False
    if row.ignored and not include_ignored:
        return False
    if row.flag == "ignored" and not include_ignored:
        return False
    return True


def build_appearance_row(
    *,
    profile: SpeakerProfileV1,
    link: SpeakerProfileLinkV1,
    resolver: ManagedTranscriptResolver,
    include_ignored: bool = False,
) -> AppearanceRow:
    del include_ignored  # flag construction is independent; eligibility uses it later
    key = link_file_key(link.managed_transcript_id, link.local_speaker_key)
    ignored = False
    current_relpath: str | None = None
    appearance_date: date | None = None
    metrics = OccurrenceMetrics(
        words=0,
        turns=0,
        duration_seconds=None,
        avg_turn_duration=None,
        median_turn_duration=None,
        wpm=None,
    )
    speaking_share = None
    speaking_share_basis: SpeakingShareBasis = "unavailable"
    repair_required = False
    missing_source = False
    collision = False
    needs_review = False
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
        raws = {str(s.get("speaker")).strip() for s in keyed if s.get("speaker")}
        collision = len(raws) > 1
        fp = compute_occurrence_fingerprint(keyed)
        needs_review = fp != link.occurrence_fingerprint
        ignored = _is_ignored(resolved.transcript_path, link.local_speaker_key)
        metrics = compute_occurrence_metrics(keyed)
        denom = _transcript_duration_denominator(segments)
        if metrics.duration_seconds is not None and denom is not None and denom > 0:
            speaking_share = metrics.duration_seconds / denom
            speaking_share_basis = "duration"
    except UnresolvedManagedTranscriptError:
        missing_source = True
    except (RepairRequiredError, CorruptLinkError):
        repair_required = True
    except Exception:
        missing_source = True

    flag = resolve_appearance_flag(
        repair_required=repair_required,
        missing_source=missing_source,
        collision=collision,
        needs_review=needs_review,
        ignored=ignored,
    )

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
        speaking_share=speaking_share,
        speaking_share_basis=speaking_share_basis,
    )


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
    headline = [r for r in rows if headline_eligible(r, include_ignored=include_ignored)]
    total_duration = 0.0
    for r in headline:
        if r.metrics.duration_seconds is not None:
            total_duration += r.metrics.duration_seconds
    enriched: list[AppearanceRow] = []
    headline_turns = sum(h.metrics.turns for h in headline)
    for r in rows:
        turn_share = None
        if headline_eligible(r, include_ignored=include_ignored) and headline_turns > 0:
            turn_share = r.metrics.turns / headline_turns
        # speaking_share already transcript-relative from build_appearance_row
        enriched.append(replace(r, turn_share=turn_share))

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
        speaking_share_basis="unavailable",
        headline_turn_share=None,
        appearance_count=len(enriched),
        headline_appearance_count=len(headline),
        pending_review_count=sum(1 for r in enriched if r.flag == "needs_review"),
        missing_source_count=sum(1 for r in enriched if r.flag == "missing_source"),
        ignored_linked_count=sum(
            1 for r in enriched if r.ignored or r.flag == "ignored"
        ),
        collision_count=sum(1 for r in enriched if r.flag == "collision"),
        repair_required_count=sum(1 for r in enriched if r.flag == "repair_required"),
        appearances=tuple(enriched),
        freshness_token=freshness,
    )


def list_profile_links(profile_id: str, *, root: Path) -> list[SpeakerProfileLinkV1]:
    return list(_scan_links(root).links_by_profile.get(profile_id, ()))


@dataclass(frozen=True)
class LinkScanResult:
    links_by_profile: dict[str, list[SpeakerProfileLinkV1]]
    corrupt_paths: tuple[str, ...]
    all_links: tuple[SpeakerProfileLinkV1, ...]


def _scan_links(root: Path) -> LinkScanResult:
    links_root = links_dir(root)
    if not links_root.is_dir():
        return LinkScanResult(links_by_profile={}, corrupt_paths=(), all_links=())
    out: dict[str, list[SpeakerProfileLinkV1]] = {}
    all_links: list[SpeakerProfileLinkV1] = []
    corrupt: list[str] = []
    for path in sorted(links_root.glob("*.speaker_link.json")):
        try:
            link = parse_model(SpeakerProfileLinkV1, path)
        except Exception:
            corrupt.append(str(path))
            continue
        all_links.append(link)
        out.setdefault(link.profile_id, []).append(link)
    return LinkScanResult(
        links_by_profile=out,
        corrupt_paths=tuple(corrupt),
        all_links=tuple(all_links),
    )


def list_profiles(*, root: Path) -> list[ProfileListItem]:
    """Legacy listing helper — prefer AggregationSnapshot for Speakers UI."""
    from transcriptx.core.speaker_profiles.operations import relative_profile_path
    from transcriptx.core.speaker_profiles.recovery import blocking_operations_index

    pref = profiles_dir(root)
    if not pref.is_dir():
        return []
    link_scan = _scan_links(root)
    blocked_by_path = blocking_operations_index(root)
    incomplete = bool(link_scan.corrupt_paths)
    items: list[ProfileListItem] = []
    for path in sorted(pref.glob("*.speaker_profile.json")):
        try:
            profile = parse_model(SpeakerProfileV1, path)
        except Exception:
            incomplete = True
            continue
        links = link_scan.links_by_profile.get(profile.profile_id, ())
        blocked = blocked_by_path.get(relative_profile_path(profile.profile_id), ())
        for link in links:
            key = link_file_key(link.managed_transcript_id, link.local_speaker_key)
            from transcriptx.core.speaker_profiles.operations import relative_link_path

            if blocked_by_path.get(relative_link_path(key)):
                blocked = list(blocked) + blocked_by_path[relative_link_path(key)]
        items.append(
            ProfileListItem(
                profile_id=profile.profile_id,
                display_name=profile.display_name,
                status=profile.status,
                merged_into_profile_id=profile.merged_into_profile_id,
                updated_at=profile.updated_at,
                link_count=len(links),
                needs_repair=bool(blocked),
                aliases=tuple(profile.aliases),
                accent_color=profile.accent_color,
                incomplete=incomplete,
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
