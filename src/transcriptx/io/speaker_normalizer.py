"""
Speaker normalization for VTT and SRT imports.

This module handles extraction and normalization of speaker hints from VTT and SRT cues,
mapping them to standardized SPEAKER_XX format or null if no speaker info exists.
"""

from typing import Any, Dict, List, Optional, Union

from transcriptx.core.utils.logger import get_logger
from transcriptx.io.vtt_parser import VTTCue
from transcriptx.io.srt_parser import SRTCue

logger = get_logger()

# Type alias for cue objects that have speaker hints
CueWithSpeaker = Union[VTTCue, SRTCue]


def extract_speaker_hints(cue: CueWithSpeaker) -> Optional[str]:
    """
    Extract speaker hint from a VTT or SRT cue.

    Args:
        cue: VTTCue or SRTCue object

    Returns:
        Speaker hint string or None
    """
    return cue.speaker_hint


def assign_speaker_ids(speaker_hints: List[Optional[str]]) -> Dict[str, str]:
    """
    Create mapping from unique speaker hints to SPEAKER_XX format.

    Args:
        speaker_hints: List of speaker hints (may contain None)

    Returns:
        Dictionary mapping original speaker hint to SPEAKER_XX format
    """
    # Get unique non-None speaker hints
    unique_speakers = []
    seen = set()
    for hint in speaker_hints:
        if hint and hint not in seen:
            unique_speakers.append(hint)
            seen.add(hint)

    # Create mapping
    mapping = {}
    for idx, speaker in enumerate(sorted(unique_speakers)):
        speaker_id = f"SPEAKER_{idx:02d}"
        mapping[speaker] = speaker_id

    return mapping


def normalize_speakers(cues: List[CueWithSpeaker]) -> List[Dict[str, Any]]:
    """
    Normalize speaker hints from VTT or SRT cues to segments with SPEAKER_XX format.

    Rules:
    - If no speaker info: speaker is null (don't fake diarization)
    - If speaker hints present: normalize to SPEAKER_XX format
    - Preserve original speaker names in metadata

    Args:
        cues: List of VTTCue or SRTCue objects

    Returns:
        List of segment dictionaries with normalized speakers
    """
    # Extract all speaker hints
    speaker_hints = [extract_speaker_hints(cue) for cue in cues]

    # Check if any speaker hints exist
    has_speakers = any(hint is not None for hint in speaker_hints)

    if not has_speakers:
        # No speaker info - set all to null
        logger.info("No speaker hints found, setting speaker to null for all segments")
        segments = []
        for cue in cues:
            segment = {
                "start": cue.start,
                "end": cue.end,
                "speaker": None,
                "text": cue.text,
            }
            if cue.id:
                segment["cue_id"] = cue.id
            # Only VTTCue has settings attribute
            if hasattr(cue, "settings") and cue.settings:
                segment["original_cue"] = {"settings": cue.settings}
            segments.append(segment)
        return segments

    # Create speaker mapping
    speaker_mapping = assign_speaker_ids(speaker_hints)

    # Log speaker mapping for reference
    logger.info(f"Found {len(speaker_mapping)} unique speakers")
    for original, normalized in speaker_mapping.items():
        logger.debug(f"  {original} -> {normalized}")

    # Convert cues to segments with normalized speakers
    segments = []
    for cue in cues:
        speaker_hint = extract_speaker_hints(cue)
        normalized_speaker = speaker_mapping.get(speaker_hint) if speaker_hint else None

        segment = {
            "start": cue.start,
            "end": cue.end,
            "speaker": normalized_speaker,
            "text": cue.text,
        }

        # Add optional fields
        if cue.id:
            segment["cue_id"] = cue.id

        # Preserve original cue data in metadata
        original_cue_data = {}
        # Only VTTCue has settings attribute
        if hasattr(cue, "settings") and cue.settings:
            original_cue_data["settings"] = cue.settings
        if speaker_hint:
            original_cue_data["original_speaker"] = speaker_hint
        if original_cue_data:
            segment["original_cue"] = original_cue_data

        segments.append(segment)

    return segments
