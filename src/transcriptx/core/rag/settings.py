"""Configuration for RAG index, embedding, and retrieval."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class RagSettings:
    """Configuration for RAG subsystem.

    Replaces Paperful's Config with TX-specific fields.
    Read from environment or persisted Settings (P1).
    """

    # Data paths
    data_dir: Path
    """Base data directory; index lives under data_dir/rag/<provider>__<model>/"""

    # Embedding model (Ollama or LiteLLM)
    embed_provider: str = "ollama"
    """'ollama' (default, local) or 'litellm' (hosted; user explicitly enables)."""

    embed_model: str = "nomic-embed-text"
    """Embedding model tag. Default: nomic-embed-text (multilingual, ~100M params)."""

    embed_dim: int = 768
    """Embedding dimension (nomic-embed-text is 768; bge-m3 is 1024)."""

    # Embedding server
    ollama_base_url: str = "http://localhost:11434"
    """Base URL for Ollama (or other OpenAI-compatible embed server)."""

    litellm_base_url: Optional[str] = None
    """LiteLLM base URL if using hosted embeddings (rare, requires user opt-in)."""

    # Retrieval
    top_k: int = 5
    """Top K passages to retrieve per question."""

    # Chunking
    chunk_chars: int = 512
    """Target chunk size in characters (segments may be merged to this budget)."""

    min_chunk_chars: int = 128
    """Minimum chunk size; never chunk smaller."""

    chunk_overlap_chars: int = 100
    """Overlap between chunks for context preservation."""

    chunker_version: str = "v1"
    """Chunker algorithm version for ledger invalidation on changes."""

    # Context window for answering
    max_context_chars: int = 3000
    """Max characters to include in prompt context (stops at chunk boundaries)."""

    # Chat model (reuses TRANSCRIPTX_LLM settings when enabled)
    llm_model: Optional[str] = None
    """Chat model for answering. If None, uses default from LLMClient."""

    llm_timeout_s: float = 30.0
    """Timeout for LLM calls."""

    llm_max_num_ctx: int = 4096
    """Max context window for LLM."""

    # Feature gates
    enabled: bool = False
    """Disable RAG entirely if False (TRANSCRIPTX_RAG_ENABLED env var)."""

    auto_ingest: bool = False
    """Auto-ingest on transcript admit (P1); manual button for P0."""

    hybrid_search: bool = True
    """Use hybrid vector + FTS search (Paperful pattern); fallback to vector-only if FTS unavailable."""

    # Metadata
    schema_version: str = "v1"
    """Schema version for meta.json; bump on breaking changes."""

    @property
    def index_dir(self) -> Path:
        """Directory for this embed model's index."""
        fingerprint = f"{self.embed_provider}__{self.embed_model}"
        return self.data_dir / "rag" / fingerprint

    @property
    def lancedb_dir(self) -> Path:
        """LanceDB table directory."""
        return self.index_dir / "lancedb"

    @property
    def ledger_path(self) -> Path:
        """Ingest ledger (JSONL of transcript sources and sha/mtime/params)."""
        return self.index_dir / "ingest.jsonl"

    @property
    def meta_path(self) -> Path:
        """Index metadata (schema version, dim, model fingerprint)."""
        return self.index_dir / "meta.json"
