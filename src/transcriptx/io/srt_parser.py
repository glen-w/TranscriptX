"""
SRT parser for TranscriptX.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from transcriptx.core.utils.logger import get_logger

logger = get_logger()


@dataclass
class SRTCue:
    start: float
    end: float
    text: str
    id: Optional[str] = None
    speaker_hint: Optional[str] = None


def parse_srt_timestamp(timestamp: str) -> float:
    timestamp = timestamp.strip()

    match = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", timestamp)
    if match:
        hours, minutes, seconds, milliseconds = map(int, match.groups())
        return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0

    match = re.match(r"(\d{2}):(\d{2}),(\d{3})", timestamp)
    if match:
        minutes, seconds, milliseconds = map(int, match.groups())
        return minutes * 60 + seconds + milliseconds / 1000.0

    raise ValueError(f"Invalid timestamp format: {timestamp}")


def _extract_speaker_hint(text: str) -> tuple[Optional[str], str]:
    match = re.match(r"^([A-Z][A-Za-z\s]+?):\s*(.*)", text)
    if match:
        speaker = match.group(1).strip()
        cleaned = match.group(2).strip()
        if len(speaker) <= 50 and (not speaker.isupper() or len(speaker) <= 20):
            return speaker, cleaned
    return None, text


def parse_srt_file(path: str | Path) -> List[SRTCue]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"SRT file not found: {path}")

    with open(path, "r", encoding="utf-8") as handle:
        lines = [line.rstrip("\n") for line in handle]

    cues: List[SRTCue] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        cue_id: Optional[str] = None
        if line.isdigit():
            cue_id = line
            i += 1
            if i >= len(lines):
                break
            line = lines[i].strip()

        if "-->" not in line:
            logger.warning(f"Expected timestamp line, got: {line}")
            i += 1
            continue

        start_str, end_str = [part.strip() for part in line.split("-->", 1)]

        try:
            start = parse_srt_timestamp(start_str)
            end = parse_srt_timestamp(end_str)
        except ValueError as exc:
            logger.warning(f"Failed to parse timestamp line '{line}': {exc}")
            i += 1
            continue

        i += 1
        text_lines: List[str] = []
        while i < len(lines) and lines[i].strip():
            text_lines.append(lines[i].strip())
            i += 1

        i += 1
        text = "\n".join(text_lines).strip()
        if not text:
            continue

        speaker_hint, cleaned_text = _extract_speaker_hint(text)
        cues.append(
            SRTCue(
                id=cue_id,
                start=start,
                end=end,
                text=cleaned_text,
                speaker_hint=speaker_hint,
            )
        )

    return cues
