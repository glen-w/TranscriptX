"""Segment-preserving chunk windows for corrections LLM discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence


@dataclass(frozen=True)
class TranscriptChunk:
    chunk_index: int
    segment_indices: List[int]
    segments: List[Dict[str, Any]]


def build_segment_chunks(
    segments: Sequence[Dict[str, Any]],
    *,
    chunk_max_segments: int = 40,
    chunk_overlap_segments: int = 4,
    max_chunks: int = 25,
) -> List[TranscriptChunk]:
    n = len(segments)
    if n == 0:
        return []
    size = max(1, int(chunk_max_segments))
    overlap = max(0, min(int(chunk_overlap_segments), size - 1))
    step = max(1, size - overlap)
    out: List[TranscriptChunk] = []
    start = 0
    idx = 0
    while start < n and idx < max_chunks:
        end = min(n, start + size)
        indices = list(range(start, end))
        out.append(
            TranscriptChunk(
                chunk_index=idx,
                segment_indices=indices,
                segments=[segments[i] for i in indices],
            )
        )
        idx += 1
        if end >= n:
            break
        start += step
    return out
