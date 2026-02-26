"""Speaker mapping module."""

import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from colorama import Fore, init
from rich.console import Console

from transcriptx.core.utils.logger import get_logger
from transcriptx.utils.text_utils import is_named_speaker

# Lazy imports to avoid circular dependencies:
# - choose_mapping_action imported in load_or_create_speaker_map
# - offer_and_edit_tags imported in load_or_create_speaker_map

# Initialize colorama for cross-platform colored output
init(autoreset=True)

# Color cycle for speaker identification
# Each speaker gets a distinct color during the mapping process
COLOR_CYCLE = [
    Fore.CYAN,
    Fore.MAGENTA,
    Fore.YELLOW,
    Fore.GREEN,
    Fore.BLUE,
    Fore.LIGHTRED_EX,
]

console = Console()
logger = get_logger()


@dataclass(frozen=True)
class SegmentRef:
    text: str
    start: Optional[float]
    end: Optional[float]

    @property
    def has_timestamps(self) -> bool:
        return self.start is not None and self.end is not None


def compute_speaker_stats_from_segments(
    segments: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Compute per-speaker stats in one pass over segments.

    For each segment, _extract_segment_times is called once. Segment missing
    end (or invalid times) is ignored for duration but still counts as a segment.
    Percent uses duration if total_duration > 0 else segment count.

    Returns:
        Dict mapping speaker_id to {segment_count, total_duration, percent}.
    """
    by_speaker: Dict[str, Dict[str, Any]] = {}
    total_duration: float = 0.0
    total_segments: int = 0

    for seg in segments:
        speaker_id = seg.get("speaker")
        if speaker_id is None:
            continue
        if speaker_id not in by_speaker:
            by_speaker[speaker_id] = {"segment_count": 0, "total_duration": 0.0}
        by_speaker[speaker_id]["segment_count"] += 1
        total_segments += 1

        start, end = _extract_segment_times(seg)
        if start is not None and end is not None and end >= start:
            dur = end - start
            by_speaker[speaker_id]["total_duration"] += dur
            total_duration += dur

    for data in by_speaker.values():
        if total_duration > 0:
            data["percent"] = 100.0 * data["total_duration"] / total_duration
        else:
            data["percent"] = (
                100.0 * data["segment_count"] / total_segments
                if total_segments
                else 0.0
            )

    return by_speaker


def _extract_segment_times(
    segment: Dict[str, Any],
) -> tuple[Optional[float], Optional[float]]:
    """Extract segment start/end seconds from common fields."""
    start = segment.get("start")
    end = segment.get("end")
    if start is None and "start_time" in segment:
        start = segment.get("start_time")
    if end is None and "end_time" in segment:
        end = segment.get("end_time")
    if start is None and "start_ms" in segment:
        start = float(segment.get("start_ms", 0)) / 1000.0
    if end is None and "end_ms" in segment:
        end = float(segment.get("end_ms", 0)) / 1000.0
    try:
        start = float(start) if start is not None else None
    except (TypeError, ValueError):
        start = None
    try:
        end = float(end) if end is not None else None
    except (TypeError, ValueError):
        end = None
    return start, end


def _format_lines_for_display(
    segments: List[SegmentRef],
    displayed_indices: List[int],
    selected_offset: int,
) -> List[tuple[str, str]]:
    if not displayed_indices:
        return [("", "(no lines available)\n")]
    formatted: List[tuple[str, str]] = []
    for offset, seg_idx in enumerate(displayed_indices):
        seg = segments[seg_idx]
        marker = ">" if offset == selected_offset else " "
        timestamp_note = " ⛔ no timestamps" if not seg.has_timestamps else ""
        text = seg.text.strip()
        formatted.append(("", f"{marker} {offset + 1}. {text}{timestamp_note}\n"))
    return formatted


def _parse_user_input(text: str) -> tuple[str, Optional[str]]:
    cleaned = text.strip()
    if not cleaned:
        return "empty", None
    lowered = cleaned.lower()
    if lowered in {"m", "more", "next"}:
        return "more", None
    return "name", cleaned


def _is_test_environment() -> bool:
    """
    Check if running in test environment.

    Returns:
        True if running in pytest or test environment, False otherwise
    """
    return "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST") is not None


def extract_speaker_text(
    segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
) -> Dict[str, List[str]]:
    """
    Extract and group text by speaker from transcript segments.

    This function processes transcript segments and organizes them by
    speaker, using speaker_db_id for grouping when available to distinguish
    speakers with the same name.

    Args:
        segments: List of transcript segments
        speaker_map: Mapping from speaker IDs to human-readable names (deprecated, kept for backward compatibility)

    Returns:
        Dictionary mapping speaker display names to lists of their text segments

    Note:
        Only includes speakers that have been properly named (not system
        placeholders like "SPEAKER_01" or "Unidentified"). This ensures
        that analysis results focus on actual human speakers rather than
        system artifacts.

        The function is commonly used for:
        - Generating speaker-specific word clouds
        - Creating speaker summaries and statistics
        - Analyzing individual speaker patterns
        - Preparing data for speaker-focused analysis modules
    """
    from transcriptx.core.utils.speaker_extraction import (
        group_segments_by_speaker,
        get_speaker_display_name,
    )

    # Group segments by speaker using speaker_db_id when available
    grouped_segments = group_segments_by_speaker(segments)

    # Extract text grouped by display name
    grouped: Dict[str, List[str]] = {}
    for grouping_key, segs in grouped_segments.items():
        display_name = get_speaker_display_name(grouping_key, segs, segments)
        if display_name and is_named_speaker(display_name):
            texts = [seg.get("text", "") for seg in segs if seg.get("text")]
            if texts:
                grouped.setdefault(display_name, []).extend(texts)

    return grouped
