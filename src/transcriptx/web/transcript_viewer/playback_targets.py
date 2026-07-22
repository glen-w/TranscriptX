"""Pure adapters for Transcript per-segment playback targets.

Overlong segments remain playable: ClipService clamps extracts to
``MAX_CLIP_DURATION_SEC`` (60s) at extraction time. This adapter does not
suppress ▶ for long ranges; it only rejects invalid timestamps.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Mapping

from transcriptx.services.speaker_studio.clip_service import MAX_CLIP_DURATION_SEC
from transcriptx.services.speaker_studio.segment_index import SegmentInfo

# Re-export for documentation / callers that need the documented cap.
CLIP_DURATION_CAP_SEC = MAX_CLIP_DURATION_SEC

# Bounded widget-key material (hex chars).
_OWNER_PREFIX_HASH_LEN = 16


def coerce_playback_timestamp(value: Any) -> float | None:
    """
    Coerce a segment timestamp for playback.

    Rejects booleans, non-numeric values, NaN, and infinity.
    """
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def format_safe_timestamp_range(
    start: Any,
    end: Any,
    format_key: str,
    *,
    format_single,
) -> str | None:
    """
    Format a timestamp range for display without raising.

    Returns None when either bound is missing/invalid or the range would be
    rejected for playback (reversed / negative end), so callers can omit the
    label while still rendering segment text.
    """
    start_f = coerce_playback_timestamp(start)
    end_f = coerce_playback_timestamp(end)
    if start_f is None or end_f is None:
        return None
    if not is_valid_playback_range(start_f, end_f):
        return None
    return f"{format_single(start_f, format_key)} - {format_single(end_f, format_key)}"


def group_timestamp_bounds(
    group_segments: list[tuple[int, Mapping[str, Any]]],
) -> tuple[float, float] | None:
    """
    Derive a Turns group range from individually valid timestamp pairs.

    Only segments whose start/end both coerce and pass
    ``is_valid_playback_range`` contribute. Uses the first valid start and
    last valid end among those pairs.
    """
    first_start: float | None = None
    last_end: float | None = None
    for _, segment in group_segments:
        if not isinstance(segment, Mapping):
            continue
        start = coerce_playback_timestamp(segment.get("start"))
        end = coerce_playback_timestamp(segment.get("end"))
        if start is None or end is None:
            continue
        if not is_valid_playback_range(start, end):
            continue
        if first_start is None:
            first_start = start
        last_end = end
    if first_start is None or last_end is None:
        return None
    return first_start, last_end


def segment_playback_speaker(segment: Mapping[str, Any]) -> str:
    """Speaker label: speaker_display, then speaker, then Unknown."""
    display = segment.get("speaker_display")
    if display is not None and str(display).strip():
        return str(display)
    speaker = segment.get("speaker")
    if speaker is not None and str(speaker).strip():
        return str(speaker)
    return "Unknown"


def segment_playback_text(segment: Mapping[str, Any]) -> str:
    """Safe string text for a segment."""
    text = segment.get("text", "")
    if text is None:
        return ""
    return str(text)


def is_valid_playback_range(start: float, end: float) -> bool:
    """Reject negative end values and non-positive durations."""
    if end < 0:
        return False
    if end <= start:
        return False
    return True


def build_playback_targets(
    display_segments: list[tuple[int, dict[str, Any]]],
) -> dict[int, SegmentInfo]:
    """
    Build validated SegmentInfo objects keyed by original source index.

    Segments with invalid timestamps are omitted (text still renders without ▶).
    Overlong ranges (``end - start > CLIP_DURATION_CAP_SEC``) are included;
    ClipService clamps duration at extraction.
    """
    targets: dict[int, SegmentInfo] = {}
    for source_index, segment in display_segments:
        if not isinstance(segment, dict):
            continue
        start = coerce_playback_timestamp(segment.get("start"))
        end = coerce_playback_timestamp(segment.get("end"))
        if start is None or end is None:
            continue
        if not is_valid_playback_range(start, end):
            continue
        targets[source_index] = SegmentInfo(
            index=source_index,
            start=start,
            end=end,
            text=segment_playback_text(segment),
            speaker=segment_playback_speaker(segment),
        )
    return targets


def ordered_playback_targets(
    display_segments: list[tuple[int, dict[str, Any]]],
    targets: Mapping[int, SegmentInfo],
) -> list[SegmentInfo]:
    """Return validated targets in filtered display order."""
    ordered: list[SegmentInfo] = []
    for source_index, _ in display_segments:
        target = targets.get(source_index)
        if target is not None:
            ordered.append(target)
    return ordered


def filtered_view_signature(
    *,
    owner_identity: tuple[Any, ...],
    display_segments: list[tuple[int, dict[str, Any]]],
    search_text: str = "",
    jump_index: int | None = None,
) -> tuple[Any, ...]:
    """
    Deterministic signature for the current filtered view.

    Includes owner identity, normalised search/jump controls, plus ordered
    source indices and rounded timestamps. Distinct queries that happen to
    produce the same index set still change the signature.
    """
    segment_sig: list[tuple[int, float | None, float | None]] = []
    for source_index, segment in display_segments:
        start = coerce_playback_timestamp(
            segment.get("start") if isinstance(segment, dict) else None
        )
        end = coerce_playback_timestamp(
            segment.get("end") if isinstance(segment, dict) else None
        )
        segment_sig.append(
            (
                source_index,
                None if start is None else round(start, 3),
                None if end is None else round(end, 3),
            )
        )
    return (
        *owner_identity,
        str(search_text or "").strip().lower(),
        jump_index,
        tuple(segment_sig),
    )


def transcript_revision_identity(path: Path) -> tuple[str, int, int]:
    """Resolved path string + size + mtime_ns for ownership / cache reset."""
    resolved = path.resolve(strict=True)
    stat = resolved.stat()
    return (str(resolved), int(stat.st_size), int(stat.st_mtime_ns))


def owner_prefix_hash(owner_identity: tuple[Any, ...]) -> str:
    """Bounded deterministic hash for Streamlit widget-key namespacing."""
    material = "\0".join(repr(part) for part in owner_identity)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return digest[:_OWNER_PREFIX_HASH_LEN]


def warm_list_position(
    ordered_targets: list[SegmentInfo],
    active_source_index: int | None,
) -> int | None:
    """Map an active source index to its position in the ordered warm list."""
    if active_source_index is None:
        return None
    if type(active_source_index) is not int:
        return None
    for position, target in enumerate(ordered_targets):
        if target.index == active_source_index:
            return position
    return None
