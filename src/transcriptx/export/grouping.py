"""Contiguous speaker grouping for transcript export and viewer."""

from __future__ import annotations

from typing import Any, Callable, Optional


def segment_speaker_label(segment: dict[str, Any]) -> str:
    return str(segment.get("speaker_display") or segment.get("speaker") or "Unknown")


def group_contiguous_segments_by_speaker(
    segments: list[dict[str, Any]],
    *,
    speaker_of: Optional[Callable[[dict[str, Any]], str]] = None,
) -> list[tuple[str, list[dict[str, Any]]]]:
    """Group contiguous transcript segments by speaker label.

    ``speaker_of`` defaults to ``speaker_display`` then ``speaker`` then
    ``\"Unknown\"``.
    """
    label_fn = speaker_of or segment_speaker_label
    groups: list[tuple[str, list[dict[str, Any]]]] = []
    current_speaker: str | None = None
    current_group: list[dict[str, Any]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        speaker = label_fn(segment)
        if speaker != current_speaker:
            if current_group:
                groups.append((str(current_speaker), current_group))
            current_speaker = speaker
            current_group = [segment]
        else:
            current_group.append(segment)
    if current_group:
        groups.append((str(current_speaker), current_group))
    return groups
