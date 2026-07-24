"""Batched embedding with TF-IDF fallback; LRU cache for text→vector."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, List, Optional

import numpy as np

from transcriptx.core.utils.logger import log_error


class LRUEmbeddingCache:
    """Bounded LRU cache mapping normalized text → embedding vector."""

    def __init__(self, maxsize: int) -> None:
        self.maxsize = max(0, int(maxsize))
        self._data: OrderedDict[str, np.ndarray] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[np.ndarray]:
        if self.maxsize == 0:
            self.misses += 1
            return None
        if key in self._data:
            self.hits += 1
            self._data.move_to_end(key)
            return self._data[key].copy()
        self.misses += 1
        return None

    def put(self, key: str, value: np.ndarray) -> None:
        if self.maxsize == 0:
            return
        self._data[key] = value.copy()
        self._data.move_to_end(key)
        while len(self._data) > self.maxsize:
            self._data.popitem(last=False)


def _l2_normalize_rows(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return mat / norms


def embed_texts_tfidf(texts: List[str]) -> np.ndarray:
    """Single global TF-IDF fit; L2-normalized rows (cosine = dot)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize

    if not texts:
        return np.zeros((0, 1), dtype=np.float64)
    vectorizer = TfidfVectorizer(max_features=4096, ngram_range=(1, 2))
    X = vectorizer.fit_transform(texts)
    dense = X.toarray().astype(np.float64)
    return normalize(dense, axis=1, norm="l2")


class SemanticBatchEmbedder:
    """
    Embed a list of texts. Uses transformers + mean pooling when torch/transformers
    are available; otherwise TF-IDF vectors.
    """

    def __init__(
        self,
        model_name: str,
        batch_size: int,
        *,
        cache: Optional[LRUEmbeddingCache] = None,
        model_manager: Any | None = None,
        transformer_unavailable_reason: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.batch_size = max(1, int(batch_size))
        self.cache = cache
        self.model_manager = model_manager
        self.transformer_unavailable_reason = transformer_unavailable_reason
        self.embedding_backend: str | None = None
        self.embedding_fallback_reason: str | None = None
        self.transformer_backend_available: bool = False
        self.embedding_device: str | None = None

    def embed_unique_texts(self, texts: List[str]) -> np.ndarray:
        """Return matrix (len(texts), d) in the same order (with optional LRU cache)."""
        if not texts:
            return np.zeros((0, 1), dtype=np.float64)

        resolved_pairs: list[tuple[int, np.ndarray]] = []
        pending_idx: list[int] = []
        pending_text: list[str] = []

        for i, t in enumerate(texts):
            cached = self.cache.get(t) if self.cache else None
            if cached is not None:
                resolved_pairs.append((i, cached))
            else:
                pending_idx.append(i)
                pending_text.append(t)

        if not pending_text:
            out = np.stack(
                [v for _, v in sorted(resolved_pairs, key=lambda x: x[0])], axis=0
            )
            return _l2_normalize_rows(out)

        fallback_reason = self._controlled_fallback_reason()
        if fallback_reason:
            emb = embed_texts_tfidf(pending_text)
            self._mark_tfidf_fallback(fallback_reason)
        else:
            try:
                emb = self._embed_transformer_batches(pending_text)
                self._mark_transformer_success()
            except (ImportError, ModuleNotFoundError):
                emb = embed_texts_tfidf(pending_text)
                self._mark_tfidf_fallback("missing_transformer_dependency")
            except Exception as exc:
                log_error(
                    "SEMANTIC_V2",
                    f"Transformer embedding inference failed: {exc}",
                    exception=exc,
                )
                raise

        if self.cache:
            for t, row in zip(pending_text, emb):
                self.cache.put(t, row)

        by_index: dict[int, np.ndarray] = {i: v for i, v in resolved_pairs}
        for idx, row in zip(pending_idx, emb):
            by_index[idx] = row
        ordered = [by_index[j] for j in range(len(texts))]
        return _l2_normalize_rows(np.stack(ordered, axis=0))

    def _controlled_fallback_reason(self) -> str | None:
        if self.transformer_unavailable_reason:
            return self.transformer_unavailable_reason
        if self.model_manager is None:
            return "model_unavailable"
        if (
            getattr(self.model_manager, "model", None) is None
            or getattr(self.model_manager, "tokenizer", None) is None
            or getattr(self.model_manager, "torch", None) is None
            or getattr(self.model_manager, "device", None) is None
        ):
            return "model_unavailable"
        return None

    def _mark_tfidf_fallback(self, reason: str) -> None:
        self.embedding_backend = "tfidf"
        self.embedding_fallback_reason = reason
        self.transformer_backend_available = False
        self.embedding_device = None

    def _mark_transformer_success(self) -> None:
        self.embedding_backend = "transformer"
        self.embedding_fallback_reason = None
        self.transformer_backend_available = True
        self.embedding_device = str(getattr(self.model_manager, "device", ""))

    def _embed_transformer_batches(self, texts: List[str]) -> np.ndarray:
        if self.model_manager is None:
            raise ImportError(
                "SemanticModelManager is required for transformer embeddings"
            )
        torch = self.model_manager.torch
        tokenizer = self.model_manager.tokenizer
        model = self.model_manager.model
        device = self.model_manager.device
        if torch is None or tokenizer is None or model is None or device is None:
            raise ImportError("Transformer backend is unavailable")

        model.eval()
        outs: list[np.ndarray] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            enc = tokenizer(
                batch,
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=256,
            )
            enc = {k: v.to(device) for k, v in enc.items()}
            with torch.no_grad():
                out = model(**enc).last_hidden_state
                mask = enc["attention_mask"].unsqueeze(-1)
                summed = (out * mask).sum(dim=1)
                counts = mask.sum(dim=1).clamp(min=1e-6)
                pooled = summed / counts
            outs.append(pooled.detach().cpu().numpy().astype(np.float64))
        return np.concatenate(outs, axis=0)
