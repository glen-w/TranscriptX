"""
Ingest pipeline: load segments → chunk → embed → index → ledger.

Orchestrates the full cycle for one transcript. Called on admit/corrections/rebuild.
"""

import os
from pathlib import Path
from typing import List

from .chunk import Chunk, chunk_segments
from .embed import EmbedError, OllamaEmbedder
from .index import Index
from .ledger import Ledger, LedgerEntry, file_mtime, file_sha256
from .settings import RagSettings


def ingest_transcript(
    transcript_path: Path,
    session_slug: str,
    run_id: str,
    transcript_title: str,
    settings: RagSettings,
    segments: List[dict],
) -> None:
    """
    Ingest one transcript: chunk, embed, and index.

    Args:
        transcript_path: Path to transcript JSON file.
        session_slug: Session identifier.
        run_id: Run within session.
        transcript_title: Human title for citation.
        settings: RagSettings (data dir, embed model, etc.).
        segments: Loaded segments from get_segments().

    Raises:
        EmbedError: If embedding fails.
        IndexError: If index operations fail.
    """
    if not settings.enabled:
        return

    # Load or create ledger
    ledger = Ledger(settings.ledger_path)

    # Compute file freshness
    file_sha = file_sha256(transcript_path)
    file_mtime_val = file_mtime(transcript_path)

    # Check if already indexed
    entry = ledger.get(session_slug, run_id)
    if entry and entry.is_fresh(
        file_sha,
        file_mtime_val,
        settings.chunker_version,
        settings.embed_model,
    ):
        # Already up to date
        return

    # Chunk segments
    chunks = chunk_segments(
        segments,
        transcript_title=transcript_title,
        session_slug=session_slug,
        run_id=run_id,
        chunk_chars=settings.chunk_chars,
        min_chunk_chars=settings.min_chunk_chars,
        source="segments",
    )

    if not chunks:
        return

    # Create or open index
    index = Index.open(
        settings,
        dim=settings.embed_dim,
        create=True,
    )

    # Embed chunks
    embedder = OllamaEmbedder(
        model=settings.embed_model,
        base_url=settings.ollama_base_url,
        timeout_s=settings.llm_timeout_s,
    )

    texts = [chunk.text for chunk in chunks]
    try:
        vectors = embedder.embed_documents(texts)
    except EmbedError as e:
        # Log error and record failed entry
        ledger.add(
            LedgerEntry(
                session_slug=session_slug,
                run_id=run_id,
                transcript_path=str(transcript_path),
                file_sha256=file_sha,
                file_mtime=file_mtime_val,
                ingested_at=0.0,
                chunker_version=settings.chunker_version,
                embed_model=settings.embed_model,
                embed_dim=settings.embed_dim,
                error=str(e),
            )
        )
        raise

    # Build LanceDB rows
    rows = []
    for chunk, vector in zip(chunks, vectors):
        rows.append(
            {
                "chunk_id": f"{session_slug}:{run_id}:{chunk.chunk_index}",
                "text": chunk.text,
                "vector": vector,
                "t_start": chunk.t_start,
                "t_end": chunk.t_end,
                "segment_index_start": chunk.segment_index_start,
                "segment_index_end": chunk.segment_index_end,
                "speakers": chunk.speakers,
                "transcript_title": chunk.transcript_title,
                "session_slug": chunk.session_slug,
                "run_id": chunk.run_id,
                "source": chunk.source,
            }
        )

    # Write to index
    index.add_chunks(rows)

    # Record in ledger
    import time

    ledger.add(
        LedgerEntry(
            session_slug=session_slug,
            run_id=run_id,
            transcript_path=str(transcript_path),
            file_sha256=file_sha,
            file_mtime=file_mtime_val,
            ingested_at=time.time(),
            chunker_version=settings.chunker_version,
            embed_model=settings.embed_model,
            embed_dim=settings.embed_dim,
            chunks_count=len(chunks),
            chunk_start_idx=chunks[0].chunk_index if chunks else 0,
            chunk_end_idx=chunks[-1].chunk_index if chunks else 0,
        )
    )
