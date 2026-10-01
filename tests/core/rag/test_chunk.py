"""Tests for segment chunking logic."""

import pytest

from transcriptx.core.rag.chunk import Chunk, chunk_segments
from transcriptx.io import load_segments


def test_chunk_segments_basic():
    """Basic chunking with real fixture."""
    segments = load_segments("tests/fixtures/mini_transcript.json")

    chunks = chunk_segments(
        segments,
        transcript_title="Mini Transcript",
        session_slug="test_session",
        run_id="run_1",
        chunk_chars=200,  # Small budget to force merging
    )

    assert len(chunks) > 0
    assert all(isinstance(c, Chunk) for c in chunks)
    assert all(c.t_start < c.t_end for c in chunks)
    assert all(c.segment_index_start <= c.segment_index_end for c in chunks)
    assert all(c.session_slug == "test_session" for c in chunks)
    assert all(c.run_id == "run_1" for c in chunks)


def test_chunk_segments_preserves_boundaries():
    """Chunks never split mid-segment."""
    segments = load_segments("tests/fixtures/mini_transcript.json")
    original_text = " ".join(seg["text"] for seg in segments)

    chunks = chunk_segments(
        segments,
        transcript_title="Mini Transcript",
        session_slug="test",
        run_id="r1",
    )

    # Reconstruct text from chunks
    chunked_text = " ".join(c.text for c in chunks)

    # Should preserve exact segment text (just reordered by chunks)
    # Count words as proxy for content preservation
    assert len(original_text.split()) == len(chunked_text.split())


def test_chunk_segments_missing_required_fields():
    """Raise ValueError if segment missing start/end."""
    bad_segments = [
        {"text": "Hello", "speaker": "Alice"},  # Missing start/end
    ]

    with pytest.raises(ValueError, match="missing 'start'"):
        chunk_segments(
            bad_segments,
            transcript_title="Bad",
            session_slug="test",
            run_id="r1",
        )


def test_chunk_segments_empty():
    """Empty segment list returns empty chunks."""
    chunks = chunk_segments(
        [],
        transcript_title="Empty",
        session_slug="test",
        run_id="r1",
    )
    assert chunks == []
