"""Embedding for transcript chunks via Ollama or LiteLLM.

Ported from Paperful pattern. Handles task prefixes, batching, normalization.
"""

import math
from dataclasses import dataclass
from typing import List, Tuple

import httpx


# Task prefixes for embedding models (model → (doc_prefix, query_prefix))
_TASK_PREFIXES = {
    "nomic-embed-text": ("search_document: ", "search_query: "),
    # Most other models (bge-m3, mxbai-embed-large, etc.) take no prefix
}


class EmbedError(Exception):
    """Embedding configuration or transport error."""

    pass


def model_base_name(model: str) -> str:
    """Extract bare model name from tag (e.g., 'nomic-embed-text:latest' → 'nomic-embed-text')."""
    name = model.strip().lower().rsplit("/", 1)[-1]  # Remove provider prefix if any
    return name.split(":", 1)[0]  # Remove tag


def task_prefixes(model: str) -> Tuple[str, str]:
    """Return (document_prefix, query_prefix) for this embedding model."""
    return _TASK_PREFIXES.get(model_base_name(model), ("", ""))


def _normalize(vector: List[float]) -> List[float]:
    """L2-normalize vector so distances are meaningful."""
    norm = math.sqrt(sum(x * x for x in vector))
    if not norm or not math.isfinite(norm):
        raise EmbedError("embedding model returned an empty or non-finite vector")
    return [x / norm for x in vector]


@dataclass
class OllamaEmbedder:
    """Embedding client for Ollama (local embedding models)."""

    model: str
    """Model tag (e.g., 'nomic-embed-text')."""

    base_url: str = "http://localhost:11434"
    """Ollama base URL."""

    batch_size: int = 32
    """Texts to embed per API call."""

    timeout_s: float = 120.0
    """HTTP timeout in seconds."""

    provider: str = "ollama"

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a batch of document texts.

        Args:
            texts: List of text strings.

        Returns:
            List of normalized embedding vectors (same length as texts).

        Raises:
            EmbedError: On API error or malformed response.
        """
        if not texts:
            return []

        doc_prefix = task_prefixes(self.model)[0]
        prefixed = [f"{doc_prefix}{text}" for text in texts]

        vectors: List[List[float]] = []
        for start in range(0, len(prefixed), self.batch_size):
            batch = prefixed[start : start + self.batch_size]
            batch_vectors = self._embed_batch(batch)

            if len(batch_vectors) != len(batch):
                raise EmbedError(
                    f"Ollama returned {len(batch_vectors)} vectors for {len(batch)} texts"
                )

            for vector in batch_vectors:
                vectors.append(_normalize([float(x) for x in vector]))

        return vectors

    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single query text.

        Args:
            text: Query text.

        Returns:
            Normalized embedding vector.
        """
        query_prefix = task_prefixes(self.model)[1]
        prefixed = f"{query_prefix}{text}"
        batch_vectors = self._embed_batch([prefixed])

        if not batch_vectors:
            raise EmbedError("Ollama returned no embeddings for query")

        return _normalize([float(x) for x in batch_vectors[0]])

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Call Ollama /api/embed for a batch of texts."""
        url = self.base_url.rstrip("/") + "/api/embed"
        payload = {"model": self.model, "input": texts, "truncate": True}

        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                resp = client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise EmbedError(f"Ollama embedding timed out after {self.timeout_s}s") from exc
        except httpx.TransportError as exc:
            raise EmbedError(f"Ollama unreachable: {exc}") from exc

        if resp.status_code == 404:
            raise EmbedError(
                f"Ollama has no embedding model {self.model!r}. "
                f"Try: ollama pull {self.model}"
            )

        if resp.status_code >= 400:
            raise EmbedError(
                f"Ollama embedding failed: HTTP {resp.status_code} {resp.text[:200]}"
            )

        try:
            vectors = resp.json().get("embeddings")
        except (ValueError, AttributeError) as exc:
            raise EmbedError(f"invalid Ollama embedding response: {exc}") from exc

        if not isinstance(vectors, list):
            raise EmbedError("Ollama embedding response has no 'embeddings' list")

        return vectors

    def check_config(self) -> Tuple[bool, str]:
        """
        Check if Ollama is reachable and model is installed.

        Returns:
            (is_ok, message) where is_ok is True if ready.
        """
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(self.base_url.rstrip("/") + "/api/tags")
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            return False, f"Ollama unreachable at {self.base_url}: {exc}"

        names = [m.get("name", "") for m in (data.get("models") or [])]
        if not any(n == self.model or n.startswith(f"{self.model}:") for n in names):
            return False, (
                f"embedding model {self.model!r} not in Ollama. "
                f"Try: ollama pull {self.model}"
            )

        return True, "ok"

    @property
    def dimension(self) -> int:
        """Infer dimension from first embed call (P0; could be cached later)."""
        # For now, known dimensions:
        # - nomic-embed-text: 768
        # - bge-m3: 1024
        # P1: Cache after first embed
        base = model_base_name(self.model)
        if base == "nomic-embed-text":
            return 768
        if base == "bge-m3":
            return 1024
        # Fallback: assume 768 and let index validation catch mismatch
        return 768
