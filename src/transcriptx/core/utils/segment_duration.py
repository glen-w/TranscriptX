"""Dependency-neutral per-speaker segment duration helpers.

Shared by stats and interactions so eligible-speaker filtering and duration
summation rules stay aligned without cross-module imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from transcriptx.utils.text_utils import is_eligible_named_speaker


def valid_segment_duration(segment: Mapping[str, Any]) -> float | None:
    """
    Return a non-negative duration for a segment, or None if timestamps are invalid.

    Rules:
    - Missing or non-numeric start/end → None (skip; do not coerce to a fake zero)
    - end < start → None (negative duration)
    - end == start → 0.0 (valid zero-duration segment)
    - Overlaps are not collapsed; callers sum raw lengths (claimed speaking time)
    """
    start_raw = segment.get("start")
    end_raw = segment.get("end")
    if start_raw is None or end_raw is None:
        return None
    try:
        start = float(start_raw)
        end = float(end_raw)
    except (TypeError, ValueError):
        return None
    if end < start:
        return None
    return end - start


@dataclass(frozen=True)
class SpeakerDurationResult:
    """Eligible speakers and valid summed speaking durations."""

    durations: dict[str, float]
    eligible_speakers: tuple[str, ...]
    speaker_segments: dict[str, list[dict[str, Any]]]
    speaker_key_map: dict[str, str]
    skipped_segments: int = 0
    allow_fallback_speakers: bool = False
    total_valid_duration: float = 0.0
    diagnostics: dict[str, Any] = field(default_factory=dict)


def compute_eligible_speaker_durations(
    segments: Sequence[Mapping[str, Any]],
    *,
    ignored_ids: set[str] | None = None,
    grouped_hint: Mapping[str, Any] | None = None,
) -> SpeakerDurationResult:
    """
    Build eligible speaker roster and valid summed speaking durations from segments.

    Eligibility matches speaker_stats: ``is_eligible_named_speaker`` on display names
    from segment grouping, with anonymized-label fallback when no named speakers
    exist and ``grouped_hint`` is non-empty (same gate as stats).
    """
    from transcriptx.core.utils.speaker_extraction import (
        get_speaker_display_name,
        group_segments_by_speaker,
    )

    ignored = ignored_ids or set()
    segment_list = [dict(seg) for seg in segments]
    grouped_segments = group_segments_by_speaker(segment_list)

    speaker_segments_map: dict[str, list[dict[str, Any]]] = {}
    speaker_key_map: dict[str, str] = {}
    for grouping_key, segs in grouped_segments.items():
        display_name = get_speaker_display_name(grouping_key, segs, segment_list)
        if display_name and is_eligible_named_speaker(
            display_name, str(grouping_key), ignored
        ):
            speaker_segments_map[display_name] = list(segs)
            speaker_key_map[display_name] = str(grouping_key)

    allow_fallback = False
    if not speaker_segments_map and grouped_hint:
        allow_fallback = True
        for seg in segment_list:
            name = str(seg.get("speaker") or "").strip()
            if not name:
                continue
            if ignored and (
                name in ignored or str(seg.get("speaker_db_id")) in ignored
            ):
                continue
            speaker_segments_map.setdefault(name, []).append(seg)
            speaker_key_map.setdefault(name, name)

    durations: dict[str, float] = {}
    skipped = 0
    for name, segs in speaker_segments_map.items():
        total = 0.0
        for seg in segs:
            dur = valid_segment_duration(seg)
            if dur is None:
                skipped += 1
                continue
            total += dur
        durations[name] = total

    # Deterministic eligible roster (sorted display names)
    eligible = tuple(sorted(speaker_segments_map.keys()))
    total_valid = sum(durations.values())

    return SpeakerDurationResult(
        durations=durations,
        eligible_speakers=eligible,
        speaker_segments=speaker_segments_map,
        speaker_key_map=speaker_key_map,
        skipped_segments=skipped,
        allow_fallback_speakers=allow_fallback,
        total_valid_duration=total_valid,
        diagnostics={"skipped_invalid_timestamps": skipped},
    )
