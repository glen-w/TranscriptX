"""
Speaker extraction utilities for TranscriptX.

This module provides centralized utilities for extracting speaker information
from transcript segments, using a stable per-speaker id when present
for grouping and distinguishing speakers with the same name.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from transcriptx.io.speaker_map_resolver import normalize_diarized_id
from transcriptx.utils.text_utils import is_named_speaker, is_turn_taking_speaker_label

_SPEAKER_DISPLAY_MAP: Optional[Dict[str, str]] = None


def set_speaker_display_map(mapping: Dict[str, str]) -> None:
    global _SPEAKER_DISPLAY_MAP
    _SPEAKER_DISPLAY_MAP = mapping


def clear_speaker_display_map() -> None:
    global _SPEAKER_DISPLAY_MAP
    _SPEAKER_DISPLAY_MAP = None


@dataclass
class SpeakerInfo:
    """Speaker information extracted from segment."""

    grouping_key: Union[str, int]  # speaker_db_id if available, else speaker name
    display_name: str  # speaker name, possibly disambiguated
    db_id: Optional[
        int
    ]  # Stable numeric id from segment JSON when present (legacy key: speaker_db_id)


def extract_speaker_info(segment: Dict[str, Any]) -> Optional[SpeakerInfo]:
    """
    Extract speaker information from segment.

    Priority:
    1. speaker_db_id (canonical identifier) - use for grouping
    2. speaker name - use for display and fallback grouping
    3. original_speaker_id - legacy support

    Args:
        segment: Transcript segment dictionary

    Returns:
        SpeakerInfo if speaker found, None otherwise
    """
    # Check for speaker_db_id first (canonical identifier)
    db_id = segment.get("speaker_db_id")
    if db_id is not None:
        # Use db_id as grouping key
        grouping_key = int(db_id)
        # Get display name from speaker field
        display_name = segment.get("speaker", str(db_id))
        # Only use name if it's a named speaker, otherwise use ID
        if not display_name or not is_named_speaker(display_name):
            display_name = f"Speaker {db_id}"
        return SpeakerInfo(
            grouping_key=grouping_key, display_name=display_name, db_id=db_id
        )

    # Fall back to speaker name
    speaker_name = segment.get("speaker")
    if speaker_name and is_named_speaker(speaker_name):
        return SpeakerInfo(
            grouping_key=speaker_name, display_name=speaker_name, db_id=None
        )

    # Legacy: try original_speaker_id
    original_id = segment.get("original_speaker_id")
    if original_id:
        return SpeakerInfo(
            grouping_key=original_id, display_name=original_id, db_id=None
        )

    return None


def count_named_speakers(
    segments: List[Dict[str, Any]],
    *,
    ignored_speaker_ids: Optional[set[Union[str, int]]] = None,
) -> int:
    """
    Count distinct named speakers using stable identifiers when available.

    Args:
        segments: Transcript segments to inspect.
        ignored_speaker_ids: Optional set of speaker IDs to exclude from the count.

    Returns:
        Number of distinct named speakers.
    """
    ignored = ignored_speaker_ids or set()
    named_speaker_ids: set[Union[str, int]] = set()

    for segment in segments:
        info = extract_speaker_info(segment)
        if info is None:
            continue

        display_name = get_speaker_display_name(info.grouping_key, [segment], segments)
        if not display_name or not is_named_speaker(display_name):
            continue

        speaker_id = info.db_id if info.db_id is not None else info.grouping_key
        if speaker_id in ignored or str(speaker_id) in ignored:
            continue

        if speaker_id is None:
            speaker_id = display_name

        named_speaker_ids.add(speaker_id)

    return len(named_speaker_ids)


def count_turn_taking_speakers(
    segments: List[Dict[str, Any]],
    *,
    ignored_speaker_ids: Optional[set[Union[str, int]]] = None,
) -> int:
    """
    Count distinct speakers eligible for turn-taking analysis.

    Unlike :func:`count_named_speakers`, diarization-style labels such as
    ``SPEAKER_00`` are counted as distinct speakers. Bare unknown placeholders
    are excluded (see :func:`is_turn_taking_speaker_label`). This is the count
    used to gate modules that analyse interaction structure rather than only
    human-named participants.

    Args:
        segments: Transcript segments to inspect.
        ignored_speaker_ids: Optional set of speaker IDs to exclude from the count.

    Returns:
        Number of distinct turn-taking speakers.
    """
    ignored = ignored_speaker_ids or set()
    speaker_keys: set[Union[str, int]] = set()

    for segment in segments:
        label = segment.get("speaker")
        if not label or not is_turn_taking_speaker_label(str(label)):
            continue

        db_id = segment.get("speaker_db_id")
        key: Union[str, int] = int(db_id) if db_id is not None else str(label)
        if key in ignored or str(key) in ignored:
            continue

        speaker_keys.add(key)

    return len(speaker_keys)


def get_unique_speakers(segments: List[Dict[str, Any]]) -> Dict[Union[str, int], str]:
    """
    Get unique speakers from segments.

    Returns: Dict mapping grouping_key (db_id or name) -> display_name
    If same names exist, display_name includes disambiguation (e.g., "Glen (ID: 5)")

    Args:
        segments: List of transcript segments

    Returns:
        Dictionary mapping grouping_key -> display_name
    """
    # First pass: collect all speakers with their info
    speaker_infos: Dict[Union[str, int], SpeakerInfo] = {}
    name_counts: Dict[str, int] = {}

    for segment in segments:
        info = extract_speaker_info(segment)
        if info is None:
            continue

        # Track by grouping key
        if info.grouping_key not in speaker_infos:
            speaker_infos[info.grouping_key] = info
            # Count occurrences of each name
            name_counts[info.display_name] = name_counts.get(info.display_name, 0) + 1

    # Second pass: disambiguate same names
    result: Dict[Union[str, int], str] = {}
    name_to_keys: Dict[str, List[Union[str, int]]] = {}

    # Group keys by display name
    for key, info in speaker_infos.items():
        name = info.display_name
        if name not in name_to_keys:
            name_to_keys[name] = []
        name_to_keys[name].append(key)

    # Build result with disambiguation
    for key, info in speaker_infos.items():
        name = info.display_name
        # If multiple speakers have same name, disambiguate with ID
        if name_to_keys[name] and len(name_to_keys[name]) > 1 and info.db_id:
            display_name = f"{name} (ID: {info.db_id})"
        else:
            display_name = name
        result[key] = display_name

    return result


def group_segments_by_speaker(
    segments: List[Dict[str, Any]],
) -> Dict[Union[str, int], List[Dict[str, Any]]]:
    """
    Group segments by speaker using speaker_db_id when available.

    Args:
        segments: List of transcript segments

    Returns:
        Dictionary mapping grouping_key -> list of segments
    """
    grouped: Dict[Union[str, int], List[Dict[str, Any]]] = {}

    for segment in segments:
        info = extract_speaker_info(segment)
        if info is None:
            continue

        key = info.grouping_key
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(segment)

    return grouped


def get_speaker_display_name(
    grouping_key: Union[str, int],
    segments: List[Dict[str, Any]],
    all_segments: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Get display name for a speaker, disambiguating if needed.

    Args:
        grouping_key: The grouping key (db_id or name)
        segments: Segments for this speaker
        all_segments: All segments in transcript (for disambiguation check)

    Returns:
        Display name, disambiguated if needed
    """
    if isinstance(grouping_key, str) and _SPEAKER_DISPLAY_MAP:
        normalized = normalize_diarized_id(grouping_key)
        mapped_name = None
        if normalized:
            mapped_name = _SPEAKER_DISPLAY_MAP.get(normalized)
        if mapped_name is None:
            mapped_name = _SPEAKER_DISPLAY_MAP.get(grouping_key)
        if mapped_name:
            return f"{mapped_name} ({grouping_key})"

    if isinstance(grouping_key, int) and _SPEAKER_DISPLAY_MAP and segments:
        for seg in segments:
            for field in ("speaker", "original_speaker_id"):
                raw = seg.get(field)
                if raw is None:
                    continue
                nid = normalize_diarized_id(raw)
                if nid and nid in _SPEAKER_DISPLAY_MAP:
                    mapped_name = _SPEAKER_DISPLAY_MAP[nid]
                    return f"{mapped_name} ({grouping_key})"

    if not segments:
        return str(grouping_key)

    # Get base name from first segment
    base_name = segments[0].get("speaker", str(grouping_key))
    db_id = segments[0].get("speaker_db_id")

    # Check if disambiguation is needed
    if all_segments is None:
        all_segments = segments

    # Count how many speakers have the same name
    same_name_count = sum(
        1
        for seg in all_segments
        if seg.get("speaker") == base_name and seg.get("speaker_db_id") != db_id
    )

    # Disambiguate if multiple speakers have same name and we have db_id
    if same_name_count > 0 and db_id is not None:
        return f"{base_name} (ID: {db_id})"

    return base_name if base_name and is_named_speaker(base_name) else str(grouping_key)


def named_speaker_count_for_path(path) -> int:
    """
    Return named speaker count for a transcript file using sidecar-backed
    speaker-map semantics.
    """
    from transcriptx.io.speaker_map_resolver import SpeakerMapResolver

    path_str = str(path)
    resolver = SpeakerMapResolver()
    return resolver.load_mapping(path_str).named_speaker_count
