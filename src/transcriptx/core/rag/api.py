"""Thin API boundary for Streamlit Ask page.

Exposes: ingest, search, answer, status. All no-ops if RAG disabled.
"""

import os
from pathlib import Path
from typing import List, Optional

from transcriptx.core.llm import get_llm_client
from transcriptx.core.utils.config import get_config

from .answer import AnswerStream, answer as _answer
from .embed import OllamaEmbedder
from .index import Index, IndexMissing
from .ingest import ingest_transcript
from .ledger import Ledger
from .retrieve import Hit, search as _search
from .settings import RagSettings


class RagAPI:
    """Thin API for Streamlit Ask page."""

    def __init__(self, settings: Optional[RagSettings] = None):
        """
        Initialize RAG API.

        Args:
            settings: RagSettings (defaults to building from env/config).
        """
        if settings is None:
            data_dir = Path(
                os.environ.get(
                    "TRANSCRIPTX_DATA_DIR",
                    "./data",
                )
            )
            settings = RagSettings(
                data_dir=data_dir,
                enabled=os.environ.get("TRANSCRIPTX_RAG_ENABLED", "0") == "1",
                embed_model=os.environ.get(
                    "TRANSCRIPTX_RAG_EMBED_MODEL", "nomic-embed-text"
                ),
                ollama_base_url=os.environ.get(
                    "TRANSCRIPTX_OLLAMA_BASE_URL",
                    "http://localhost:11434",
                ),
            )

        self.settings = settings

    def is_enabled(self) -> bool:
        """Check if RAG is enabled."""
        return self.settings.enabled

    def ingest(
        self,
        transcript_path: Path,
        session_slug: str,
        run_id: str,
        transcript_title: str,
        segments: List[dict],
    ) -> None:
        """Ingest one transcript."""
        if not self.is_enabled():
            return

        ingest_transcript(
            Path(transcript_path),
            session_slug,
            run_id,
            transcript_title,
            self.settings,
            segments,
        )

    def search(
        self,
        question: str,
        session_slug: Optional[str] = None,
        run_id: Optional[str] = None,
        k: int = 5,
    ) -> List[Hit]:
        """Search index for relevant chunks."""
        if not self.is_enabled():
            return []

        try:
            index = Index.open(self.settings, create=False)
        except IndexMissing:
            return []

        embedder = OllamaEmbedder(
            model=self.settings.embed_model,
            base_url=self.settings.ollama_base_url,
        )

        query_vector = embedder.embed_query(question)
        results = index.search(query_vector, k=k)

        # Convert LanceDB rows to Hit objects
        hits = []
        for row in results:
            hit = Hit(
                chunk_index=row.get("chunk_index", 0),
                text=row.get("text", ""),
                score=row.get("_distance", 0.0),
                t_start=row.get("t_start", 0.0),
                t_end=row.get("t_end", 0.0),
                segment_index_start=row.get("segment_index_start", 0),
                segment_index_end=row.get("segment_index_end", 0),
                speakers=row.get("speakers", []),
                transcript_title=row.get("transcript_title", ""),
                session_slug=row.get("session_slug", ""),
                run_id=row.get("run_id", ""),
                source=row.get("source", "segments"),
            )
            hits.append(hit)

        return hits

    def answer(
        self,
        question: str,
        session_slug: Optional[str] = None,
        run_id: Optional[str] = None,
        k: int = 5,
    ) -> AnswerStream:
        """Answer a question from the index."""
        if not self.is_enabled():
            # Return empty answer
            def empty_gen():
                yield "RAG is not enabled."

            from .prompt import Source

            return AnswerStream(empty_gen(), [], [])

        # Search
        hits = self.search(question, session_slug, run_id, k=k)

        # Answer
        client = get_llm_client()
        return _answer(question, hits=hits, client=client)

    def index_status(self) -> dict:
        """Check if index exists and is fresh."""
        if not self.is_enabled():
            return {"enabled": False}

        try:
            index = Index.open(self.settings, create=False)
        except IndexMissing:
            return {"enabled": True, "status": "missing"}

        ledger = Ledger(self.settings.ledger_path)
        return {
            "enabled": True,
            "status": "ok",
            "model": index.model,
            "dim": index.dim,
            "ledger_entries": len(ledger.entries),
        }
