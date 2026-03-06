"""
Segment coalescing for VTT imports.

This module provides optional post-processing to merge adjacent subtitle chunks
based on configurable criteria (gap size, max duration, max characters).
"""

from dataclasses import dataclass
from typing import Any, Dict, List

from transcriptx.core.utils.logger import get_logger

logger = get_logger()


@dataclass
class CoalesceConfig:
    """Configuration for segment coalescing."""

    enabled: bool = False
    max_gap_ms: float = 500.0  # Merge if gap < X ms
    max_duration_seconds: float = 30.0  # Cap max segment duration
    max_characters: int = 500  # Cap max characters per segment
    preserve_cue_boundaries: bool = True  # Keep original boundaries in metadata


def coalesce_segments(
    segments: List[Dict[str, Any]], config: CoalesceConfig
) -> List[Dict[str, Any]]:
    """
    Merge segments based on configuration.

    Behavior:
    - Only merge if gap between segments < max_gap_ms
    - Respect max duration and character limits
    - Preserve original cue boundaries in metadata if preserve_cue_boundaries=True

    Args:
        segments: List of segment dictionaries
        config: Coalescing configuration

    Returns:
        List of coalesced segments
    """
    if not config.enabled or not segments:
        return segments

    coalesced = []
    current_segment = None
    original_boundaries = []

    for segment in segments:
        if current_segment is None:
            # Start new segment
            current_segment = segment.copy()
            original_boundaries = [
                {
                    "start": segment["start"],
                    "end": segment["end"],
                }
            ]
            continue

        # Calculate gap between current segment end and next segment start
        gap_ms = (segment["start"] - current_segment["end"]) * 1000

        # Check if we should merge
        should_merge = (
            gap_ms < config.max_gap_ms
            and gap_ms >= 0  # Don't merge overlapping segments
        )

        if should_merge:
            # Check constraints
            new_duration = segment["end"] - current_segment["start"]
            new_text = current_segment["text"] + " " + segment["text"]
            new_char_count = len(new_text)

            # Check if merging would exceed limits
            exceeds_duration = new_duration > config.max_duration_seconds
            exceeds_chars = new_char_count > config.max_characters

            # Also check if speakers match (don't merge different speakers)
            speakers_match = current_segment.get("speaker") == segment.get("speaker")

            if not exceeds_duration and not exceeds_chars and speakers_match:
                # Merge segments
                current_segment["end"] = segment["end"]
                current_segment["text"] = new_text
                original_boundaries.append(
                    {
                        "start": segment["start"],
                        "end": segment["end"],
                    }
                )
                continue

        # Can't merge - save current segment and start new one
        if config.preserve_cue_boundaries and len(original_boundaries) > 1:
            if "original_cue" not in current_segment:
                current_segment["original_cue"] = {}
            current_segment["original_cue"]["coalesced_from"] = original_boundaries

        coalesced.append(current_segment)

        # Start new segment
        current_segment = segment.copy()
        original_boundaries = [
            {
                "start": segment["start"],
                "end": segment["end"],
            }
        ]

    # Add final segment
    if current_segment is not None:
        if config.preserve_cue_boundaries and len(original_boundaries) > 1:
            if "original_cue" not in current_segment:
                current_segment["original_cue"] = {}
            current_segment["original_cue"]["coalesced_from"] = original_boundaries
        coalesced.append(current_segment)

    if len(coalesced) < len(segments):
        logger.info(
            f"Coalesced {len(segments)} segments into {len(coalesced)} segments"
        )

    return coalesced
