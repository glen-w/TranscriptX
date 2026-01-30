"""
WebVTT parser for TranscriptX.

This module provides a WebVTT-correct parser that handles all VTT features:
- Timestamps in HH:MM:SS.mmm and MM:SS.mmm formats
- Cue IDs
- Cue settings (align, position, etc.)
- NOTE and STYLE blocks
- Multi-line cue text
- Speaker hints in <v Name> format
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from transcriptx.core.utils.logger import get_logger

logger = get_logger()


@dataclass
class VTTCue:
    """Represents a parsed VTT cue."""

    start: float  # Start time in seconds
    end: float  # End time in seconds
    text: str  # Cue text (with tags stripped)
    id: Optional[str] = None  # Cue ID line
    settings: Optional[Dict[str, str]] = None  # Cue settings (align, position, etc.)
    raw_text: Optional[str] = None  # Original text with tags preserved
    speaker_hint: Optional[str] = None  # Extracted from <v Name> or NAME: patterns


def parse_vtt_timestamp(timestamp: str) -> float:
    """
    Parse a VTT timestamp to seconds.

    Handles both formats:
    - HH:MM:SS.mmm (standard)
    - MM:SS.mmm (short format, hours default to 00)

    Args:
        timestamp: Timestamp string (e.g., "00:00:05.500" or "00:05.500")

    Returns:
        Time in seconds as float

    Raises:
        ValueError: If timestamp format is invalid
    """
    # Remove any whitespace
    timestamp = timestamp.strip()

    # Try standard format HH:MM:SS.mmm
    match = re.match(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})", timestamp)
    if match:
        hours, minutes, seconds, milliseconds = map(int, match.groups())
        return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0

    # Try short format MM:SS.mmm
    match = re.match(r"(\d{2}):(\d{2})\.(\d{3})", timestamp)
    if match:
        minutes, seconds, milliseconds = map(int, match.groups())
        return minutes * 60 + seconds + milliseconds / 1000.0

    raise ValueError(f"Invalid timestamp format: {timestamp}")


def parse_cue_settings(settings_str: str) -> Dict[str, str]:
    """
    Parse cue settings from a settings string.

    Example: "align:start position:10%" -> {"align": "start", "position": "10%"}

    Args:
        settings_str: Settings string

    Returns:
        Dictionary of setting key-value pairs
    """
    settings = {}
    if not settings_str or not settings_str.strip():
        return settings

    # Split by space and parse key:value pairs
    for part in settings_str.strip().split():
        if ":" in part:
            key, value = part.split(":", 1)
            settings[key] = value

    return settings


def extract_speaker_hint(text: str) -> tuple[Optional[str], str]:
    """
    Extract speaker hint from text and return cleaned text.

    Handles patterns:
    - <v Speaker Name>text
    - SPEAKER: text
    - Name: text

    Args:
        text: Text that may contain speaker hint

    Returns:
        Tuple of (speaker_hint or None, cleaned_text)
    """
    # Pattern 1: <v Speaker Name>text
    match = re.match(r"<v\s+([^>]+)>(.*)", text, re.IGNORECASE)
    if match:
        speaker = match.group(1).strip()
        cleaned = match.group(2).strip()
        return speaker, cleaned

    # Pattern 2: SPEAKER: text or Name: text (at start of line)
    match = re.match(r"^([A-Z][A-Za-z\s]+?):\s*(.*)", text)
    if match:
        speaker = match.group(1).strip()
        cleaned = match.group(2).strip()
        # Only treat as speaker if it looks like a name (not too long, not all caps unless short)
        if len(speaker) <= 50 and (not speaker.isupper() or len(speaker) <= 20):
            return speaker, cleaned

    return None, text


def strip_html_tags(text: str) -> str:
    """
    Strip HTML-like tags from text while preserving content.

    Args:
        text: Text with potential HTML tags

    Returns:
        Text with tags removed
    """
    # Remove HTML tags but preserve content
    text = re.sub(r"<[^>]+>", "", text)
    # Clean up extra whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_vtt_file(path: str | Path) -> List[VTTCue]:
    """
    Parse a WebVTT file and return list of cues.

    Handles:
    - WEBVTT header
    - Cue IDs (optional line before timestamp)
    - Timestamps with settings
    - Multi-line cue text
    - NOTE blocks (skipped)
    - STYLE blocks (skipped)
    - Overlapping/out-of-order cues (preserved with warning)

    Args:
        path: Path to VTT file

    Returns:
        List of VTTCue objects

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"VTT file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    cues: List[VTTCue] = []
    i = 0
    line_num = 0

    # Skip WEBVTT header
    while i < len(lines) and lines[i].strip().upper() in ("WEBVTT", ""):
        i += 1
        line_num += 1

    # Track for overlap/order detection
    last_end_time = -1.0
    overlapping_count = 0
    out_of_order_count = 0

    while i < len(lines):
        line = lines[i].strip()
        line_num = i + 1

        # Skip empty lines
        if not line:
            i += 1
            continue

        # Skip NOTE blocks
        if line.upper().startswith("NOTE"):
            # Skip until blank line
            while i < len(lines) and lines[i].strip():
                i += 1
            i += 1
            continue

        # Skip STYLE blocks
        if line.upper().startswith("STYLE"):
            # Skip until blank line
            while i < len(lines) and lines[i].strip():
                i += 1
            i += 1
            continue

        # Check for cue ID (optional line before timestamp)
        cue_id: Optional[str] = None
        if i < len(lines) - 1:
            # Check if next line looks like a timestamp
            next_line = lines[i + 1].strip()
            if "-->" in next_line:
                cue_id = line
                i += 1
                line_num = i + 1
                line = lines[i].strip()

        # Parse timestamp line: "00:00:00.000 --> 00:00:05.500 [settings]"
        if "-->" not in line:
            logger.warning(
                f"Line {line_num}: Expected timestamp line with '-->', got: {line}"
            )
            i += 1
            continue

        parts = line.split("-->", 1)
        if len(parts) != 2:
            logger.warning(f"Line {line_num}: Invalid timestamp format: {line}")
            i += 1
            continue

        try:
            start_str = parts[0].strip()
            end_and_settings = parts[1].strip()

            # Parse end time and settings
            end_parts = end_and_settings.split(None, 1)
            end_str = end_parts[0]
            settings_str = end_parts[1] if len(end_parts) > 1 else ""

            start_time = parse_vtt_timestamp(start_str)
            end_time = parse_vtt_timestamp(end_str)
            settings = parse_cue_settings(settings_str) if settings_str else None

        except ValueError as e:
            logger.warning(f"Line {line_num}: Error parsing timestamp: {e}")
            i += 1
            continue

        # Check for overlaps/out-of-order
        if start_time < last_end_time:
            out_of_order_count += 1
        elif start_time < last_end_time - 0.1:  # Small overlap threshold
            overlapping_count += 1

        last_end_time = max(last_end_time, end_time)

        # Collect cue text (multi-line until blank line)
        i += 1
        text_lines = []
        while i < len(lines) and lines[i].strip():
            text_lines.append(lines[i].rstrip())
            i += 1

        # Skip blank line after cue
        if i < len(lines):
            i += 1

        # Combine text lines
        raw_text = "\n".join(text_lines)

        # Extract speaker hint and clean text
        speaker_hint, cleaned_text = extract_speaker_hint(raw_text)

        # Strip HTML tags from cleaned text
        text = strip_html_tags(cleaned_text)

        # Skip empty cues
        if not text:
            continue

        cue = VTTCue(
            id=cue_id if cue_id else None,
            start=start_time,
            end=end_time,
            text=text,
            settings=settings,
            raw_text=raw_text,
            speaker_hint=speaker_hint,
        )

        cues.append(cue)

    # Warn about overlaps/out-of-order if found
    if overlapping_count > 0:
        logger.warning(f"Found {overlapping_count} overlapping cues in VTT file")
    if out_of_order_count > 0:
        logger.warning(f"Found {out_of_order_count} out-of-order cues in VTT file")

    return cues
