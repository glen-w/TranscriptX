"""Window and block builders for insight eligibility."""

from __future__ import annotations

from typing import Any, Dict, List

from .content_filter import FilteredSegment


def _window_payload(items: List[FilteredSegment], index: int) -> Dict[str, Any]:
    text = " ".join(seg.content_text for seg in items).strip()
    return {
        "window_id": f"window_{index}",
        "text": text,
        "segment_indexes": [seg.segment_index for seg in items],
        "speakers": sorted({seg.speaker for seg in items if seg.speaker}),
        "start": min(seg.start for seg in items),
        "end": max(seg.end for seg in items),
    }


def build_rolling_windows(
    segments: List[FilteredSegment],
    *,
    window_size: int = 5,
    stride: int = 2,
) -> List[Dict[str, Any]]:
    """Build canonical rolling windows for topic modeling."""
    if not segments:
        return []
    windows: List[Dict[str, Any]] = []
    index = 0
    while index < len(segments):
        chunk = segments[index : index + window_size]
        if not chunk:
            break
        payload = _window_payload(chunk, len(windows))
        if payload["text"]:
            windows.append(payload)
        if index + window_size >= len(segments):
            break
        index += max(1, stride)
    windows.sort(key=lambda item: (item["start"], item["end"], item["window_id"]))
    return windows


def build_speaker_blocks(segments: List[FilteredSegment]) -> List[Dict[str, Any]]:
    """Build same-speaker contiguous blocks for recurrence signals."""
    if not segments:
        return []
    blocks: List[Dict[str, Any]] = []
    current: List[FilteredSegment] = []
    current_speaker = ""

    for segment in segments:
        speaker = segment.speaker or "__unknown__"
        if not current:
            current = [segment]
            current_speaker = speaker
            continue
        if speaker == current_speaker:
            current.append(segment)
            continue
        blocks.append(
            {
                "block_id": f"speaker_block_{len(blocks)}",
                "speaker": current_speaker,
                "text": " ".join(seg.content_text for seg in current),
                "segment_indexes": [seg.segment_index for seg in current],
                "start": min(seg.start for seg in current),
                "end": max(seg.end for seg in current),
            }
        )
        current = [segment]
        current_speaker = speaker

    if current:
        blocks.append(
            {
                "block_id": f"speaker_block_{len(blocks)}",
                "speaker": current_speaker,
                "text": " ".join(seg.content_text for seg in current),
                "segment_indexes": [seg.segment_index for seg in current],
                "start": min(seg.start for seg in current),
                "end": max(seg.end for seg in current),
            }
        )

    blocks.sort(key=lambda item: (item["start"], item["speaker"], item["block_id"]))
    return blocks
