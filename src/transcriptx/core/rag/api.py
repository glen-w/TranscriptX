"""Thin API boundary for Streamlit Ask page.

Exposes: ingest, search, answer, status. All no-ops if RAG disabled.
"""

import os
from pathlib import Path
from typing import Any, List, Optional

from transcriptx.core.llm import get_llm_client

from .answer import AnswerStream, answer as _answer
from .embed import OllamaEmbedder
from .flags import ollama_base_url_from_env, parse_rag_enabled
from .index import Index, IndexMissing, RagScopeMissing, RagUnavailable, scope_where
from .ingest import ingest_transcript
from .ledger import Ledger
from .retrieve import Hit
from .settings import RagSettings


class RagAPI:
    """Thin API for Streamlit Ask page."""

    def __init__(
        self,
        settings: Optional[RagSettings] = None,
        embedder: Optional[Any] = None,
    ):
        """
        Initialize RAG API.

        Args:
            settings: RagSettings (defaults to building from env/config).
            embedder: Optional embedder (tests inject a fake; default is Ollama).
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
                enabled=parse_rag_enabled(os.environ.get("TRANSCRIPTX_RAG_ENABLED")),
                embed_model=os.environ.get(
                    "TRANSCRIPTX_RAG_EMBED_MODEL", "nomic-embed-text"
                ),
                ollama_base_url=ollama_base_url_from_env(),
            )

        self.settings = settings
        self._embedder = embedder

    def is_enabled(self) -> bool:
        """Check if RAG is enabled."""
        return self.settings.enabled

    def _require_scope(self, session_slug: Optional[str], run_id: Optional[str]) -> None:
        if not session_slug or not run_id:
            raise RagScopeMissing()

    def _embedder_or_default(self) -> Any:
        if self._embedder is not None:
            return self._embedder
        return OllamaEmbedder(
            model=self.settings.embed_model,
            base_url=self.settings.ollama_base_url,
        )

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
            embedder=self._embedder_or_default(),
        )

    def search(
        self,
        question: str,
        session_slug: Optional[str] = None,
        run_id: Optional[str] = None,
        k: int = 5,
    ) -> List[Hit]:
        """Search index for relevant chunks (scoped to one transcript)."""
        if not self.is_enabled():
            return []

        self._require_scope(session_slug, run_id)

        try:
            index = Index.open(self.settings, create=False)
        except IndexMissing:
            return []

        embedder = self._embedder_or_default()
        query_vector = embedder.embed_query(question)
        results = index.search(
            query_vector, k=k, where=scope_where(str(session_slug), str(run_id))
        )

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
            def empty_gen():
                yield "RAG is not enabled."

            return AnswerStream(empty_gen(), [], [])

        self._require_scope(session_slug, run_id)
        hits = self.search(question, session_slug, run_id, k=k)

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
        except RagUnavailable:
            return {"enabled": True, "status": "unavailable"}

        ledger = Ledger(self.settings.ledger_path)
        return {
            "enabled": True,
            "status": "ok",
            "model": index.model,
            "dim": index.dim,
            "ledger_entries": len(ledger.entries),
        }
