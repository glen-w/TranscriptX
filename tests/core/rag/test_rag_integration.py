"""Integration test: ingest → search → answer → cite-jump."""

import pytest
from pathlib import Path

from transcriptx.core.rag import RagAPI, Ledger
from transcriptx.core.segments import get_segments
from transcriptx.core.rag.settings import RagSettings


@pytest.fixture
def rag_settings(tmp_path):
    """Temporary RAG settings for testing."""
    return RagSettings(
        data_dir=tmp_path,
        enabled=True,
        embed_model="nomic-embed-text",
        ollama_base_url="http://localhost:11434",
    )


@pytest.fixture
def api(rag_settings):
    """RagAPI instance with temp settings."""
    return RagAPI(rag_settings)


def test_rag_disabled_returns_empty(tmp_path):
    """RAG disabled → no-ops."""
    settings = RagSettings(data_dir=tmp_path, enabled=False)
    api = RagAPI(settings)

    assert not api.is_enabled()
    assert api.search("test") == []
    assert api.index_status()["enabled"] is False


def test_ledger_roundtrip(rag_settings):
    """Ledger save/load preserves entries."""
    from transcriptx.core.rag.ledger import LedgerEntry
    import time

    ledger = Ledger(rag_settings.ledger_path)
    entry = LedgerEntry(
        session_slug="test_session",
        run_id="run_1",
        transcript_path="/path/to/transcript.json",
        file_sha256="abc123",
        file_mtime=time.time(),
        ingested_at=time.time(),
        chunker_version="v1",
        embed_model="nomic-embed-text",
        embed_dim=768,
        chunks_count=10,
    )
    ledger.add(entry)

    # Reload
    ledger2 = Ledger(rag_settings.ledger_path)
    retrieved = ledger2.get("test_session", "run_1")
    assert retrieved is not None
    assert retrieved.chunks_count == 10


def test_chunk_segments_smoke(rag_settings):
    """Smoke test: load fixture → chunk → validate."""
    from transcriptx.core.rag.chunk import chunk_segments

    segments = get_segments("tests/fixtures/mini_transcript.json")
    chunks = chunk_segments(
        segments,
        transcript_title="Mini",
        session_slug="test",
        run_id="r1",
        chunk_chars=200,
    )

    assert len(chunks) > 0
    assert all(c.t_start >= 0 for c in chunks)
    assert all(c.session_slug == "test" for c in chunks)
    assert all(c.run_id == "r1" for c in chunks)


def test_source_has_segment_ref(rag_settings):
    """Source can build SegmentRef for navigation."""
    from transcriptx.core.rag.prompt import Source
    from transcriptx.core.rag.retrieve import Hit

    hit = Hit(
        chunk_index=0,
        text="Hello",
        score=0.95,
        t_start=0.0,
        t_end=5.0,
        segment_index_start=0,
        segment_index_end=0,
        speakers=["Alice"],
        transcript_title="Test",
        session_slug="sess",
        run_id="run1",
    )

    source = Source(marker="S1", hit=hit)
    segment_ref = source.segment_ref

    assert segment_ref.segment_index == 0
    assert segment_ref.timecode == 0.0
    assert segment_ref.transcript_ref.session_slug == "sess"
