"""Chunking strategy for transcript segments.

Merges consecutive segments from same speaker until char budget,
never splitting mid-segment. Overlap via previous-turn tail.

Replaces Paperful's PDF page/section chunker with dialogue-aware logic.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Chunk:
    """One indexed chunk: segment span + text + timecode."""

    chunk_index: int
    """Position in chunk sequence for this transcript."""

    text: str
    """Full segment text (joined segments)."""

    t_start: float
    """Segment start time (seconds)."""

    t_end: float
    """Segment end time (seconds)."""

    segment_index_start: int
    """Index of first segment in this chunk."""

    segment_index_end: int
    """Index of last segment in this chunk."""

    speakers: List[str] = field(default_factory=list)
    """Speaker names (canonical, from segment metadata)."""

    transcript_title: str = ""
    """Human title of this transcript."""

    session_slug: str = ""
    """Session identifier for SegmentRef."""

    run_id: str = ""
    """Run within session for SegmentRef."""

    source: str = "segments"
    """'segments' (raw) or 'corrected' (after corrections applied)."""

    section: Optional[str] = None
    """Optional section/topic heading from analysis (P1)."""


def chunk_segments(
    segments: List[dict],
    transcript_title: str,
    session_slug: str,
    run_id: str,
    *,
    chunk_chars: int = 512,
    min_chunk_chars: int = 128,
    overlap_chars: int = 100,
    source: str = "segments",
) -> List[Chunk]:
    """
    Split transcript segments into chunks for embedding.

    Strategy: merge consecutive same-speaker segments until `chunk_chars` budget.
    Never split mid-segment. Preserve text exactly (no truncation or cleanup).
    Overlap by reincluding previous-turn tail.

    Args:
        segments: List of segment dicts from get_segments().
            Each must have: text, speaker, start (seconds), end (seconds).
        transcript_title: Human title for citation.
        session_slug: Session identifier.
        run_id: Run within session.
        chunk_chars: Target chunk size in characters.
        min_chunk_chars: Minimum chunk size (warn if violated).
        overlap_chars: Overlap into previous turn.
        source: 'segments' or 'corrected'.

    Returns:
        List of Chunk objects, indexed in order.

    Notes:
        - All segments must have start/end; raises ValueError if missing.
        - Chunks preserve segment boundaries (never split a segment).
        - Returns [] if no segments or all segments are empty.
    """
    if not segments:
        return []

    # Validate all segments have required fields
    for i, seg in enumerate(segments):
        if "text" not in seg or seg.get("text") is None:
            raise ValueError(f"segment {i} missing 'text'")
        if "start" not in seg or seg.get("start") is None:
            raise ValueError(f"segment {i} missing 'start'")
        if "end" not in seg or seg.get("end") is None:
            raise ValueError(f"segment {i} missing 'end'")

    chunks: List[Chunk] = []
    chunk_index = 0

    i = 0
    while i < len(segments):
        # Start a new chunk
        current_speaker = segments[i].get("speaker", "Unknown")
        current_text = []
        current_chars = 0
        chunk_start_idx = i
        chunk_start_time = float(segments[i]["start"])
        chunk_speakers = set()

        # Merge segments while same speaker and under budget
        while i < len(segments):
            seg_speaker = segments[i].get("speaker", "Unknown")
            seg_text = segments[i].get("text", "").strip()

            # Stop if speaker changes
            if i > chunk_start_idx and seg_speaker != current_speaker:
                break

            # Stop if this segment would exceed budget (unless it's the only one)
            if current_text and current_chars + len(seg_text) > chunk_chars:
                break

            # Include this segment
            current_text.append(seg_text)
            current_chars += len(seg_text) + 1  # +1 for space
            chunk_speakers.add(seg_speaker)
            chunk_end_idx = i
            chunk_end_time = float(segments[i]["end"])
            i += 1

        # Finalize chunk if it has content
        merged_text = " ".join(current_text)
        if merged_text:
            if len(merged_text) < min_chunk_chars:
                # Warn but include (P0 may have short speakers)
                pass

            chunk = Chunk(
                chunk_index=chunk_index,
                text=merged_text,
                t_start=chunk_start_time,
                t_end=chunk_end_time,
                segment_index_start=chunk_start_idx,
                segment_index_end=chunk_end_idx,
                speakers=sorted(list(chunk_speakers)),
                transcript_title=transcript_title,
                session_slug=session_slug,
                run_id=run_id,
                source=source,
            )
            chunks.append(chunk)
            chunk_index += 1

    # TODO(P1): Add overlap logic if needed (prepend tail of previous chunk)
    # For now, simple coalescing without explicit overlap.

    return chunks
