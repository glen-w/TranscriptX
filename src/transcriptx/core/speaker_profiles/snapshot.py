"""Authoritative AggregationSnapshot for Speakers listing and charts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

from transcriptx.core.speaker_profiles.aggregates import (
    AppearanceFlag,
    AppearanceRow,
    OccurrenceMetrics,
    ProfileAggregate,
    ProfileListItem,
    compute_occurrence_metrics,
    headline_eligible,
)
from transcriptx.core.speaker_profiles.dates import appearance_date_from_sources
from transcriptx.core.speaker_profiles.discovery import (
    SpeakerOccurrence,
    discover_occurrences_for_resolved,
)
from transcriptx.core.speaker_profiles.errors import (
    CorruptLinkError,
    RepairRequiredError,
    UnresolvedManagedTranscriptError,
)
from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.integrity import run_integrity_scan
from transcriptx.core.speaker_profiles.layout import links_dir, profiles_dir
from transcriptx.core.speaker_profiles.models import (
    SpeakerProfileLinkV1,
    SpeakerProfileV1,
)
from transcriptx.core.speaker_profiles.operations import (
    relative_link_path,
    relative_profile_path,
)
from transcriptx.core.speaker_profiles.recovery import blocking_operations_index
from transcriptx.core.speaker_profiles.resolver import (
    ManagedTranscriptResolver,
    ResolvedManagedTranscript,
    load_transcript_segments,
)
from transcriptx.core.speaker_profiles.store_io import parse_model
from transcriptx.core.utils.segment_duration import valid_segment_duration
from transcriptx.io.speaker_map_resolver import (
    SpeakerMapResolver,
    normalize_diarized_id,
)


@dataclass(frozen=True)
class TranscriptBundle:
    """Memoized transcript-derived data for one managed transcript id."""

    managed_transcript_id: str
    resolved: ResolvedManagedTranscript | None
    segments: tuple[Mapping[str, Any], ...]
    occurrences: tuple[SpeakerOccurrence, ...]
    ignored_keys: frozenset[str]
    appearance_date: date | None
    transcript_duration_denominator: float | None
    metrics_by_key: Mapping[str, OccurrenceMetrics] = field(default_factory=dict)
    resolve_error: str | None = None


@dataclass(frozen=True)
class AggregationSnapshot:
    """Single-pass Speakers listing + aggregation input."""

    root: Path
    profiles: tuple[SpeakerProfileV1, ...]
    links: tuple[SpeakerProfileLinkV1, ...]
    links_by_profile: dict[str, tuple[SpeakerProfileLinkV1, ...]]
    listing: tuple[ProfileListItem, ...]
    aggregates_by_profile: dict[str, ProfileAggregate]
    appearances_by_profile: dict[str, tuple[AppearanceRow, ...]]
    bundles: dict[str, TranscriptBundle]
    transcript_denominators: dict[str, float]
    integrity_ok: bool
    incomplete: bool
    corrupt_profile_paths: tuple[str, ...]
    corrupt_link_paths: tuple[str, ...]
    blocked_profile_ids: frozenset[str]
    blocked_link_keys: frozenset[str]
    profiles_scanned: int
    links_scanned: int
    transcripts_resolved: int
    scan_stats: dict[str, int] = field(default_factory=dict)

    def listing_items(self) -> tuple[ProfileListItem, ...]:
        return self.listing


def _flag_precedence(
    *,
    repair_required: bool,
    missing_source: bool,
    collision: bool,
    needs_review: bool,
    ignored: bool,
) -> AppearanceFlag:
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


def _transcript_duration_denominator(segments: Sequence[Mapping[str, Any]]) -> float | None:
    total = 0.0
    any_valid = False
    for segment in segments:
        dur = valid_segment_duration(segment)
        if dur is not None:
            total += float(dur)
            any_valid = True
    return total if any_valid else None


def _load_bundle(
    managed_transcript_id: str,
    *,
    resolver: ManagedTranscriptResolver,
    speaker_map_resolver: SpeakerMapResolver,
) -> TranscriptBundle:
    try:
        resolved = resolver.resolve(managed_transcript_id)
    except Exception as exc:
        return TranscriptBundle(
            managed_transcript_id=managed_transcript_id,
            resolved=None,
            segments=(),
            occurrences=(),
            ignored_keys=frozenset(),
            appearance_date=None,
            transcript_duration_denominator=None,
            resolve_error=str(exc),
        )
    try:
        segments = tuple(load_transcript_segments(resolved.transcript_path))
        occurrences = tuple(discover_occurrences_for_resolved(resolved))
        appearance_date = appearance_date_from_sources(
            transcript_source_imported_at=resolved.source_imported_at,
            sidecar_imported_at=resolved.sidecar_imported_at,
        )
        denom = _transcript_duration_denominator(segments)
        ignored: set[str] = set()
        try:
            state = speaker_map_resolver.load_mapping(str(resolved.transcript_path))
            ignored = {
                normalize_diarized_id(x)
                for x in (state.ignored_speakers or [])
                if normalize_diarized_id(x)
            }
        except Exception:
            ignored = set()
        metrics_by_key: dict[str, OccurrenceMetrics] = {}
        for occ in occurrences:
            keyed = [
                s
                for s in segments
                if normalize_diarized_id(s.get("speaker")) == occ.local_speaker_key
            ]
            metrics_by_key[occ.local_speaker_key] = compute_occurrence_metrics(keyed)
        return TranscriptBundle(
            managed_transcript_id=managed_transcript_id,
            resolved=resolved,
            segments=segments,
            occurrences=occurrences,
            ignored_keys=frozenset(ignored),
            appearance_date=appearance_date,
            transcript_duration_denominator=denom,
            metrics_by_key=metrics_by_key,
            resolve_error=None,
        )
    except Exception as exc:
        return TranscriptBundle(
            managed_transcript_id=managed_transcript_id,
            resolved=resolved,
            segments=(),
            occurrences=(),
            ignored_keys=frozenset(),
            appearance_date=None,
            transcript_duration_denominator=None,
            resolve_error=str(exc),
        )


def _appearance_from_bundle(
    *,
    profile: SpeakerProfileV1,
    link: SpeakerProfileLinkV1,
    bundle: TranscriptBundle,
    link_blocked: bool,
) -> AppearanceRow:
    key = link_file_key(link.managed_transcript_id, link.local_speaker_key)
    repair_required = link_blocked
    missing_source = False
    collision = False
    needs_review = False
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
    speaking_share_basis: Any = "unavailable"

    if repair_required:
        flag = _flag_precedence(
            repair_required=True,
            missing_source=False,
            collision=False,
            needs_review=False,
            ignored=False,
        )
    elif bundle.resolve_error or bundle.resolved is None:
        missing_source = True
        flag = _flag_precedence(
            repair_required=False,
            missing_source=True,
            collision=False,
            needs_review=False,
            ignored=False,
        )
    else:
        current_relpath = bundle.resolved.current_relpath
        appearance_date = bundle.appearance_date
        occ_map = {o.local_speaker_key: o for o in bundle.occurrences}
        occ = occ_map.get(link.local_speaker_key)
        if occ is not None:
            collision = bool(occ.collision)
            needs_review = occ.occurrence_fingerprint != link.occurrence_fingerprint
            metrics = bundle.metrics_by_key.get(
                link.local_speaker_key,
                OccurrenceMetrics(
                    words=0,
                    turns=0,
                    duration_seconds=None,
                    avg_turn_duration=None,
                    median_turn_duration=None,
                    wpm=None,
                ),
            )
        else:
            # Linked key missing from discovery — treat as missing_source-ish metrics
            # but keep flag via needs_review/collision false.
            metrics = OccurrenceMetrics(
                words=0,
                turns=0,
                duration_seconds=None,
                avg_turn_duration=None,
                median_turn_duration=None,
                wpm=None,
            )
        ignored = link.local_speaker_key in bundle.ignored_keys
        denom = bundle.transcript_duration_denominator
        if (
            metrics.duration_seconds is not None
            and denom is not None
            and denom > 0
        ):
            speaking_share = metrics.duration_seconds / denom
            speaking_share_basis = "duration"
        flag = _flag_precedence(
            repair_required=False,
            missing_source=False,
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


def _aggregate_from_rows(
    profile: SpeakerProfileV1,
    rows: Sequence[AppearanceRow],
    *,
    include_ignored: bool,
) -> ProfileAggregate:
    import hashlib
    import json
    from dataclasses import replace

    headline = [r for r in rows if headline_eligible(r, include_ignored=include_ignored)]
    total_duration = sum(
        (r.metrics.duration_seconds or 0.0)
        for r in headline
        if r.metrics.duration_seconds is not None
    )
    headline_turns = sum(h.metrics.turns for h in headline)
    enriched: list[AppearanceRow] = []
    for r in rows:
        turn_share = None
        if headline_eligible(r, include_ignored=include_ignored) and headline_turns > 0:
            turn_share = r.metrics.turns / headline_turns
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


def build_aggregation_snapshot(
    *,
    root: Path,
    resolver: ManagedTranscriptResolver | None = None,
    speaker_map_resolver: SpeakerMapResolver | None = None,
    include_ignored: bool = False,
) -> AggregationSnapshot:
    root = Path(root)
    resolver = resolver or ManagedTranscriptResolver()
    speaker_map_resolver = speaker_map_resolver or SpeakerMapResolver()

    pref = profiles_dir(root)
    lref = links_dir(root)
    profile_paths = (
        list(pref.glob("*.speaker_profile.json")) if pref.is_dir() else []
    )
    link_paths = list(lref.glob("*.speaker_link.json")) if lref.is_dir() else []

    profiles: list[SpeakerProfileV1] = []
    corrupt_profiles: list[str] = []
    for path in sorted(profile_paths):
        try:
            profiles.append(parse_model(SpeakerProfileV1, path))
        except Exception:
            corrupt_profiles.append(str(path))

    links: list[SpeakerProfileLinkV1] = []
    corrupt_links: list[str] = []
    for path in sorted(link_paths):
        try:
            links.append(parse_model(SpeakerProfileLinkV1, path))
        except Exception:
            corrupt_links.append(str(path))

    links_by_profile: dict[str, list[SpeakerProfileLinkV1]] = {}
    for link in links:
        links_by_profile.setdefault(link.profile_id, []).append(link)

    blocked_index = blocking_operations_index(root)
    blocked_profile_ids: set[str] = set()
    blocked_link_keys: set[str] = set()
    for relpath, ops in blocked_index.items():
        if not ops:
            continue
        if relpath.startswith("profiles/") and relpath.endswith(
            ".speaker_profile.json"
        ):
            blocked_profile_ids.add(
                Path(relpath).name[: -len(".speaker_profile.json")]
            )
        elif relpath.startswith("links/") and relpath.endswith(".speaker_link.json"):
            blocked_link_keys.add(Path(relpath).name[: -len(".speaker_link.json")])

    managed_ids = sorted({lnk.managed_transcript_id for lnk in links})
    bundles: dict[str, TranscriptBundle] = {}
    for mid in managed_ids:
        bundles[mid] = _load_bundle(
            mid, resolver=resolver, speaker_map_resolver=speaker_map_resolver
        )

    transcript_denominators: dict[str, float] = {}
    for mid, bundle in bundles.items():
        if bundle.transcript_duration_denominator is not None:
            transcript_denominators[mid] = bundle.transcript_duration_denominator

    appearances_by_profile: dict[str, tuple[AppearanceRow, ...]] = {}
    aggregates_by_profile: dict[str, ProfileAggregate] = {}
    listing: list[ProfileListItem] = []

    for profile in profiles:
        plinks = links_by_profile.get(profile.profile_id, [])
        rows: list[AppearanceRow] = []
        profile_blocked = profile.profile_id in blocked_profile_ids or bool(
            blocked_index.get(relative_profile_path(profile.profile_id))
        )
        for link in plinks:
            key = link_file_key(link.managed_transcript_id, link.local_speaker_key)
            link_blocked = (
                profile_blocked
                or key in blocked_link_keys
                or bool(blocked_index.get(relative_link_path(key)))
            )
            bundle = bundles.get(link.managed_transcript_id) or TranscriptBundle(
                managed_transcript_id=link.managed_transcript_id,
                resolved=None,
                segments=(),
                occurrences=(),
                ignored_keys=frozenset(),
                appearance_date=None,
                transcript_duration_denominator=None,
                resolve_error="missing bundle",
            )
            rows.append(
                _appearance_from_bundle(
                    profile=profile,
                    link=link,
                    bundle=bundle,
                    link_blocked=link_blocked,
                )
            )
        appearances_by_profile[profile.profile_id] = tuple(rows)
        aggregates_by_profile[profile.profile_id] = _aggregate_from_rows(
            profile, rows, include_ignored=include_ignored
        )
        listing.append(
            ProfileListItem(
                profile_id=profile.profile_id,
                display_name=profile.display_name,
                status=profile.status,
                merged_into_profile_id=profile.merged_into_profile_id,
                updated_at=profile.updated_at,
                link_count=len(plinks),
                needs_repair=profile_blocked
                or any(r.flag == "repair_required" for r in rows),
                aliases=tuple(profile.aliases),
                accent_color=profile.accent_color,
                incomplete=bool(corrupt_profiles or corrupt_links),
            )
        )

    integrity = run_integrity_scan(root)
    incomplete = (
        bool(corrupt_profiles)
        or bool(corrupt_links)
        or bool(integrity.corrupt_operations)
        or not integrity.ok
    )

    return AggregationSnapshot(
        root=root,
        profiles=tuple(profiles),
        links=tuple(links),
        links_by_profile={k: tuple(v) for k, v in links_by_profile.items()},
        listing=tuple(listing),
        aggregates_by_profile=aggregates_by_profile,
        appearances_by_profile=appearances_by_profile,
        bundles=bundles,
        transcript_denominators=transcript_denominators,
        integrity_ok=integrity.ok and not corrupt_profiles and not corrupt_links,
        incomplete=incomplete,
        corrupt_profile_paths=tuple(corrupt_profiles),
        corrupt_link_paths=tuple(corrupt_links),
        blocked_profile_ids=frozenset(blocked_profile_ids),
        blocked_link_keys=frozenset(blocked_link_keys),
        profiles_scanned=len(profile_paths),
        links_scanned=len(link_paths),
        transcripts_resolved=len(bundles),
        scan_stats={
            "profile_files": len(profile_paths),
            "link_files": len(link_paths),
            "transcripts": len(bundles),
            "profiles_parsed": len(profiles),
            "links_parsed": len(links),
        },
    )
