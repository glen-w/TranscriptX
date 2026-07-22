"""Rolling windows and overlapping-chunk coverage for topic_shift."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from transcriptx.core.analysis.topic_shift.segments import CanonicalTopicSegment
from transcriptx.core.analysis.topic_shift.semantics import (
    DEFAULT_CHUNK_OVERLAP_WINDOWS,
    DEFAULT_MAX_WINDOWS_PER_CHUNK,
    DEFAULT_STRIDE,
    DEFAULT_WINDOW_SIZE,
)


@dataclass(frozen=True)
class TopicWindow:
    window_id: str
    global_index: int
    segment_indexes: tuple[int, ...]  # source_index values
    canonical_positions: tuple[int, ...]
    start: float
    end: float
    raw_text: str
    lexical_text: str


@dataclass(frozen=True)
class WindowChunk:
    chunk_id: str
    window_start_index: int
    window_end_index: int  # exclusive
    windows: tuple[TopicWindow, ...]


@dataclass(frozen=True)
class CoverageMap:
    n_canonical_segments: int
    n_windows: int
    n_chunks: int
    max_windows_per_chunk: int
    chunk_overlap_windows: int
    covered_canonical_positions: tuple[int, ...]
    complete: bool


def build_rolling_windows(
    segments: Sequence[CanonicalTopicSegment],
    *,
    window_size: int = DEFAULT_WINDOW_SIZE,
    stride: int = DEFAULT_STRIDE,
) -> list[TopicWindow]:
    """Fixed geometry rolling windows over canonical segments (own construction)."""
    if not segments:
        return []
    size = max(1, int(window_size))
    step = max(1, int(stride))
    windows: list[TopicWindow] = []
    index = 0
    n = len(segments)
    while index < n:
        chunk = list(segments[index : index + size])
        if not chunk:
            break
        raw = " ".join(seg.raw_text for seg in chunk).strip()
        if raw:
            lex = " ".join(
                tok
                for seg in chunk
                for tok in (seg.lexical_text.split() if seg.lexical_text else [])
            )
            windows.append(
                TopicWindow(
                    window_id=f"window_{len(windows)}",
                    global_index=len(windows),
                    segment_indexes=tuple(seg.source_index for seg in chunk),
                    canonical_positions=tuple(seg.canonical_position for seg in chunk),
                    start=min(seg.start for seg in chunk),
                    end=max(seg.end for seg in chunk),
                    raw_text=raw,
                    lexical_text=lex.strip(),
                )
            )
        if index + size >= n:
            break
        index += step
    windows.sort(key=lambda w: (w.start, w.end, w.window_id))
    # Reassign global_index after sort for stability
    return [
        TopicWindow(
            window_id=f"window_{i}",
            global_index=i,
            segment_indexes=w.segment_indexes,
            canonical_positions=w.canonical_positions,
            start=w.start,
            end=w.end,
            raw_text=w.raw_text,
            lexical_text=w.lexical_text,
        )
        for i, w in enumerate(windows)
    ]


def partition_overlapping_chunks(
    windows: Sequence[TopicWindow],
    *,
    max_windows_per_chunk: int = DEFAULT_MAX_WINDOWS_PER_CHUNK,
    overlap_windows: int = DEFAULT_CHUNK_OVERLAP_WINDOWS,
) -> tuple[list[WindowChunk], CoverageMap]:
    """
    Split the global window list into overlapping chunks with fixed base geometry.

    Detector resolution is unchanged; chunks only bound memory/batching.
    """
    n = len(windows)
    covered_positions: set[int] = set()
    for w in windows:
        covered_positions.update(w.canonical_positions)

    if n == 0:
        return [], CoverageMap(
            n_canonical_segments=0,
            n_windows=0,
            n_chunks=0,
            max_windows_per_chunk=max_windows_per_chunk,
            chunk_overlap_windows=overlap_windows,
            covered_canonical_positions=(),
            complete=True,
        )

    cap = max(1, int(max_windows_per_chunk))
    overlap = max(0, min(int(overlap_windows), cap - 1))
    step = max(1, cap - overlap)
    chunks: list[WindowChunk] = []
    start = 0
    while start < n:
        end = min(n, start + cap)
        slice_wins = tuple(windows[start:end])
        chunks.append(
            WindowChunk(
                chunk_id=f"chunk_{len(chunks)}",
                window_start_index=start,
                window_end_index=end,
                windows=slice_wins,
            )
        )
        if end >= n:
            break
        start += step

    # Completeness: every window appears in at least one chunk
    seen = set()
    for ch in chunks:
        for w in ch.windows:
            seen.add(w.global_index)
    complete = seen == set(range(n))

    return chunks, CoverageMap(
        n_canonical_segments=len(covered_positions),
        n_windows=n,
        n_chunks=len(chunks),
        max_windows_per_chunk=cap,
        chunk_overlap_windows=overlap,
        covered_canonical_positions=tuple(sorted(covered_positions)),
        complete=complete,
    )
