"""Retrieve relevant chunks from the index via vector + FTS search.

Returns Hit objects with segment references for citation.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:
    from transcriptx.web.models.search import SegmentRef


@dataclass
class Hit:
    """One retrieved chunk, ready for citation and context building."""

    chunk_index: int
    """Index of this chunk in the ingest sequence."""

    text: str
    """Chunk text (merged segments)."""

    score: float
    """Similarity score (0-1 scale; higher = more relevant)."""

    t_start: float
    """Segment start time (seconds)."""

    t_end: float
    """Segment end time (seconds)."""

    segment_index_start: int
    """First underlying segment index."""

    segment_index_end: int
    """Last underlying segment index."""

    speakers: List[str] = field(default_factory=list)
    """Speaker(s) in this chunk."""

    transcript_title: str = ""
    """Title of source transcript."""

    session_slug: str = ""
    """Session identifier."""

    run_id: str = ""
    """Run within session."""

    source: str = "segments"
    """'segments' or 'corrected'."""

    marker: str = ""
    """Citation marker e.g. 'S1' (assigned during prompt building)."""

    @property
    def segment_ref(self) -> "SegmentRef":
        """Build SegmentRef for navigate_to_segment().

        Uses segment_index_start as the primary locator.
        Lazy import to avoid core→web cycle.
        """
        from transcriptx.web.models.search import SegmentRef, TranscriptRef

        transcript_ref = TranscriptRef(
            session_slug=self.session_slug,
            run_id=self.run_id,
        )
        return SegmentRef(
            transcript_ref=transcript_ref,
            primary_locator="index",
            segment_index=self.segment_index_start,
            timecode=self.t_start,
        )

    @property
    def timecode_span(self) -> str:
        """Format start-end as MM:SS–MM:SS for display."""
        def seconds_to_mmss(sec: float) -> str:
            m = int(sec // 60)
            s = int(sec % 60)
            return f"{m}:{s:02d}"

        return f"{seconds_to_mmss(self.t_start)}–{seconds_to_mmss(self.t_end)}"


def search(
    index: Any,  # Index instance
    embedder: Any,  # Embedder for query embedding
    question: str,
    *,
    k: int = 5,
    session_slug: Optional[str] = None,
    run_id: Optional[str] = None,
    speaker_filter: Optional[List[str]] = None,
) -> List[Hit]:
    """
    Retrieve top-k chunks for a question.

    Args:
        index: Open Index instance.
        embedder: Embedder for encoding the question.
        question: User question.
        k: Number of results.
        session_slug: Scope to one session (current transcript).
        run_id: Scope to one run.
        speaker_filter: Filter by speaker names (P1).

    Returns:
        List of Hit objects ranked by score, descending.

    Raises:
        IndexMissing: If index not found.
    """
    # TODO(impl): Query embedding and hybrid search via LanceDB.
    # For now, return empty list (placeholder).
    # Paperful's retrieve.search takes (cfg, question, k, keys, embedder, index, ledger).
    # TX version scopes to (session_slug, run_id) instead of (collections, item_keys).
    return []
