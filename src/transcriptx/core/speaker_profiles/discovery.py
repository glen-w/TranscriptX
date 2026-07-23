"""Occurrence discovery from managed transcripts (raw local speaker keys)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from transcriptx.core.speaker_profiles.errors import (
    NotManagedTranscriptError,
    SpeakerKeyCollisionError,
)
from transcriptx.core.speaker_profiles.fingerprint import compute_occurrence_fingerprint
from transcriptx.core.speaker_profiles.identity import (
    assert_no_speaker_key_collision,
    detect_speaker_key_collisions,
    link_file_key,
    local_speaker_key_from_raw,
)
from transcriptx.core.speaker_profiles.resolver import (
    ManagedTranscriptResolver,
    ResolvedManagedTranscript,
    load_transcript_segments,
)
from transcriptx.io.speaker_map_resolver import normalize_diarized_id


@dataclass(frozen=True)
class SpeakerOccurrence:
    """Discovered speaker occurrence in one managed transcript."""

    managed_transcript_id: str
    local_speaker_key: str
    link_file_key: str
    occurrence_fingerprint: str
    raw_speakers: tuple[str, ...]
    segment_count: int
    current_relpath: str
    collision: bool = False
    collision_raw_speakers: tuple[str, ...] = ()


def discover_occurrences_from_segments(
    *,
    managed_transcript_id: str,
    current_relpath: str,
    segments: Sequence[Mapping[str, Any]],
    raise_on_collision: bool = False,
) -> list[SpeakerOccurrence]:
    """Discover occurrences from raw segments for one managed transcript."""
    by_key: dict[str, list[Mapping[str, Any]]] = {}
    raw_by_key: dict[str, set[str]] = {}
    all_raw: list[Any] = []

    for segment in segments:
        raw = segment.get("speaker")
        if raw is None:
            continue
        raw_text = str(raw).strip()
        if not raw_text:
            continue
        all_raw.append(raw)
        key = normalize_diarized_id(raw)
        if not key:
            continue
        by_key.setdefault(key, []).append(segment)
        raw_by_key.setdefault(key, set()).add(raw_text)

    collisions = detect_speaker_key_collisions(all_raw)
    if raise_on_collision and collisions:
        assert_no_speaker_key_collision(all_raw)

    occurrences: list[SpeakerOccurrence] = []
    for key, keyed_segments in sorted(by_key.items()):
        collision_raws = tuple(collisions.get(key, ()))
        occurrences.append(
            SpeakerOccurrence(
                managed_transcript_id=managed_transcript_id,
                local_speaker_key=key,
                link_file_key=link_file_key(managed_transcript_id, key),
                occurrence_fingerprint=compute_occurrence_fingerprint(keyed_segments),
                raw_speakers=tuple(sorted(raw_by_key.get(key, set()))),
                segment_count=len(keyed_segments),
                current_relpath=current_relpath,
                collision=bool(collision_raws),
                collision_raw_speakers=collision_raws,
            )
        )
    return occurrences


def discover_occurrences_for_resolved(
    resolved: ResolvedManagedTranscript,
    *,
    raise_on_collision: bool = False,
) -> list[SpeakerOccurrence]:
    """Load segments from a resolved managed transcript and discover occurrences."""
    segments = load_transcript_segments(resolved.transcript_path)
    return discover_occurrences_from_segments(
        managed_transcript_id=resolved.managed_transcript_id,
        current_relpath=resolved.current_relpath,
        segments=segments,
        raise_on_collision=raise_on_collision,
    )


def discover_occurrences_for_id(
    managed_transcript_id: str,
    resolver: ManagedTranscriptResolver,
    *,
    raise_on_collision: bool = False,
) -> list[SpeakerOccurrence]:
    """Resolve managed_transcript_id then discover occurrences."""
    resolved = resolver.resolve(managed_transcript_id)
    return discover_occurrences_for_resolved(
        resolved, raise_on_collision=raise_on_collision
    )


def discover_all_occurrences(
    resolver: ManagedTranscriptResolver,
    *,
    raise_on_collision: bool = False,
) -> list[SpeakerOccurrence]:
    """Discover occurrences across all admitted managed transcripts."""
    out: list[SpeakerOccurrence] = []
    for resolved in resolver.list_admitted():
        out.extend(
            discover_occurrences_for_resolved(
                resolved, raise_on_collision=raise_on_collision
            )
        )
    return out


def assert_occurrence_linkable(occurrence: SpeakerOccurrence) -> None:
    """Block linking when the occurrence is collision-affected."""
    if occurrence.collision:
        raise SpeakerKeyCollisionError(
            f"occurrence {occurrence.local_speaker_key!r} has colliding raw speakers "
            f"{list(occurrence.collision_raw_speakers)}; linking blocked"
        )
    # Re-validate key shape
    local_speaker_key_from_raw(occurrence.local_speaker_key)


def assert_path_eligible_for_profile_link(
    transcript_path: str | Any,
    resolver: ManagedTranscriptResolver,
) -> ResolvedManagedTranscript:
    """Managed-library gate for profile link actions (ad-hoc / run-output rejected)."""
    from pathlib import Path

    from transcriptx.core.speaker_profiles.errors import SpeakerProfilePathError

    path = Path(transcript_path)
    try:
        return resolver.resolve_path(path)
    except (NotManagedTranscriptError, SpeakerProfilePathError) as exc:
        raise NotManagedTranscriptError(
            f"profile linking requires a managed library transcript; got {path}"
        ) from exc
