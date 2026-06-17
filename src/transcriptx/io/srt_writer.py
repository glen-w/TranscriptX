"""
SRT writer for TranscriptX transcript segments.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from transcriptx.core.utils.artifact_writer import write_text

SpeakerResolver = Callable[[Mapping[str, Any]], str]


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds as an SRT timestamp: HH:MM:SS,mmm."""
    try:
        total_ms = int(round(float(seconds) * 1000))
    except (TypeError, ValueError):
        total_ms = 0

    total_ms = max(total_ms, 0)
    milliseconds = total_ms % 1000
    total_seconds = total_ms // 1000
    secs = total_seconds % 60
    total_minutes = total_seconds // 60
    mins = total_minutes % 60
    hours = total_minutes // 60

    return f"{hours:02d}:{mins:02d}:{secs:02d},{milliseconds:03d}"


def format_srt_cue(index: int, start: float, end: float, text: str) -> str:
    """Render a single SRT cue block."""
    return (
        f"{index}\n"
        f"{format_srt_timestamp(start)} --> {format_srt_timestamp(end)}\n"
        f"{text.strip()}\n\n"
    )


def segments_to_srt_text(
    segments: Iterable[Mapping[str, Any]],
    resolve_speaker: SpeakerResolver | None = None,
) -> str:
    """Convert transcript segments to SRT text, one cue per segment."""
    segment_list = [seg for seg in segments if isinstance(seg, Mapping)]
    cue_blocks: list[str] = []

    for idx, seg in enumerate(segment_list):
        start = _coerce_seconds(seg.get("start"), 0.0)
        end = _resolve_end_time(segment_list, idx, start)
        speaker = _resolve_speaker(seg, resolve_speaker)
        text = str(seg.get("text", "") or "").strip()
        cue_text = f"{speaker}: {text}" if speaker else text

        cue_blocks.append(format_srt_cue(len(cue_blocks) + 1, start, end, cue_text))

    return "".join(cue_blocks)


def write_srt_file(
    segments: Iterable[Mapping[str, Any]],
    path: str | Path,
    speaker_map: Mapping[str, str] | None = None,
    resolve_speaker: SpeakerResolver | None = None,
) -> str:
    """Write transcript segments to an SRT file and return the path."""
    if resolve_speaker is None and speaker_map:

        def _resolve_from_map(seg: Mapping[str, Any]) -> str:
            speaker_key = str(seg.get("speaker", ""))
            return str(speaker_map.get(speaker_key, seg.get("speaker", "") or ""))

        resolve_speaker = _resolve_from_map

    srt_text = segments_to_srt_text(segments, resolve_speaker)
    write_text(path, srt_text)
    return str(path)


def _coerce_seconds(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _resolve_end_time(
    segments: list[Mapping[str, Any]], index: int, start: float
) -> float:
    value = segments[index].get("end")
    if value is not None:
        return _coerce_seconds(value, start + 1.0)

    if index + 1 < len(segments):
        return _coerce_seconds(segments[index + 1].get("start"), start + 1.0)

    return start + 1.0


def _resolve_speaker(
    segment: Mapping[str, Any], resolve_speaker: SpeakerResolver | None
) -> str:
    if resolve_speaker is not None:
        return str(resolve_speaker(segment) or "").strip()

    return str(segment.get("speaker", "") or "").strip()
