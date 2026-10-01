"""LanceDB index wrapper: create, open, search, and maintain a vector store.

One index per embed model fingerprint (provider__model).
Schema: chunk_id, text, vector, t_start, t_end, segment_index_start,
        segment_index_end, speakers, transcript_title, session_slug, run_id.

Replaces Paperful's PDF-centric index.py with transcript-aware schema.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .settings import RagSettings


class IndexMissing(Exception):
    """Index not found for configured embed model."""

    pass


class IndexMismatch(Exception):
    """Index exists but metadata does not match current config."""

    pass


class RagUnavailable(Exception):
    """LanceDB not available (not installed or missing dependencies)."""

    pass


def _lancedb() -> Any:
    """Lazy import of lancedb (optional dependency)."""
    try:
        import lancedb
        return lancedb
    except ImportError:
        raise RagUnavailable(
            "lancedb not installed. Install with: pip install 'transcriptx[rag]'"
        )


class Index:
    """LanceDB index for chunks.

    Open via Index.open(settings). Provides table-level query interface.
    """

    def __init__(self, table: Any, meta: Dict[str, Any], path: Path):
        """Internal; use Index.open()."""
        self._table = table
        self.meta = meta
        self.path = path

    @property
    def dim(self) -> int:
        """Embedding dimension from metadata."""
        return int(self.meta.get("dim", 0))

    @property
    def model(self) -> str:
        """Embed model fingerprint from metadata."""
        return self.meta.get("embed_model", "unknown")

    @classmethod
    def open(
        cls,
        settings: RagSettings,
        *,
        dim: Optional[int] = None,
        create: bool = False,
    ) -> "Index":
        """
        Open or create the index for configured embed model.

        Args:
            settings: RagSettings with embed model and data paths.
            dim: Embedding dimension. Required for create=True.
            create: Create index if missing (requires dim).

        Returns:
            Open Index instance.

        Raises:
            IndexMissing: If index doesn't exist and create=False.
            IndexMismatch: If metadata doesn't match settings.
            RagUnavailable: If lancedb not installed.
        """
        lancedb = _lancedb()

        settings.index_dir.mkdir(parents=True, exist_ok=True)

        # Load or create metadata
        meta = _load_meta(settings)
        if meta is None:
            if not create:
                raise IndexMissing(
                    f"no index for {settings.embed_model!r} yet; run ingest"
                )
            if dim is None:
                raise ValueError("dim is required to create an index")
            meta = _expected_meta(settings, dim)
            _write_meta(settings, meta)

        # Validate metadata
        want = _expected_meta(settings, int(meta.get("dim", 0)))
        for name in ("embed_model", "embed_provider", "schema_version"):
            if meta.get(name) != want.get(name):
                raise IndexMismatch(
                    f"index has {name}={meta.get(name)!r}, "
                    f"settings require {want.get(name)!r}"
                )

        # Open or create LanceDB table
        db = lancedb.connect(str(settings.lancedb_dir))
        table_name = "chunks"

        try:
            table = db.open_table(table_name)
        except (FileNotFoundError, RuntimeError):
            if not create:
                raise IndexMissing(f"table {table_name} not found")
            # Will be created on first add_chunks call
            table = None

        return cls(table, meta, settings.index_dir)

    def add_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        """
        Ingest chunks (from embedding step).

        Each chunk dict should have: chunk_id, text, vector, t_start, t_end,
        segment_index_start, segment_index_end, speakers, transcript_title,
        session_slug, run_id, source.

        Creates table on first call if not yet created.
        """
        if not chunks:
            return

        lancedb = _lancedb()
        settings_from_meta = RagSettings(
            data_dir=self.path.parent.parent,  # Infer from path
            embed_model=self.meta.get("embed_model", "unknown"),
            embed_dim=int(self.meta.get("dim", 768)),
        )
        db = lancedb.connect(str(settings_from_meta.lancedb_dir))

        if self._table is None:
            # Create table on first ingest
            self._table = db.create_table("chunks", data=chunks, mode="overwrite")
        else:
            # Append chunks to existing table
            self._table.add(chunks)

    def search(
        self,
        query_vector: List[float],
        k: int = 5,
        where: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Vector search for top-k nearest chunks.

        Args:
            query_vector: Embedded query (must match dim).
            k: Top-k results.
            where: Optional LanceDB where clause for filtering.

        Returns:
            List of chunk dicts (rows), ranked by distance.
        """
        if self._table is None:
            return []

        try:
            if where:
                results = self._table.search(query_vector).where(where).limit(k).to_list()
            else:
                results = self._table.search(query_vector).limit(k).to_list()
            return results
        except Exception as e:
            # Log and return empty (P0 simple; P1 observability)
            print(f"Index search error: {e}")
            return []

    def delete_where(self, where: str) -> None:
        """
        Delete chunks matching a where clause (e.g., by session_slug/run_id).

        Used when transcript is removed or re-ingested.
        """
        if self._table is None:
            return

        try:
            self._table.delete(where)
        except Exception as e:
            print(f"Index delete error: {e}")


def _load_meta(settings: RagSettings) -> Optional[Dict[str, Any]]:
    """Load meta.json, or None if not found."""
    if not settings.meta_path.exists():
        return None

    with open(settings.meta_path, "r") as f:
        return json.load(f)


def _write_meta(settings: RagSettings, meta: Dict[str, Any]) -> None:
    """Write meta.json."""
    settings.index_dir.mkdir(parents=True, exist_ok=True)
    with open(settings.meta_path, "w") as f:
        json.dump(meta, f, indent=2)


def _expected_meta(settings: RagSettings, dim: int) -> Dict[str, Any]:
    """Construct expected metadata for validation."""
    return {
        "schema_version": settings.schema_version,
        "embed_provider": settings.embed_provider,
        "embed_model": settings.embed_model,
        "dim": dim,
        "created": time.time(),
    }
