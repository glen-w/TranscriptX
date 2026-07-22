"""Topic-shift-owned embedding backends (not SemanticBatchEmbedder)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

import numpy as np

from transcriptx.core.analysis.topic_shift.semantics import (
    DEFAULT_EN_MODEL,
    DEFAULT_MULTI_MODEL,
    PREPROCESSING_VERSION,
    BackendId,
)

BackendKind = Literal["transformers_en", "transformers_multi", "tfidf", "tfidf_char"]


@dataclass(frozen=True)
class EmbedResult:
    backend: BackendId
    model_name: str | None
    vectors: np.ndarray
    semantics_version: str
    used_fallback: bool
    fallback_reason: str | None


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return mat / norms


def embed_tfidf_word(texts: Sequence[str]) -> np.ndarray | None:
    """Corpus-fitted word TF-IDF; returns None if empty vocabulary."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize

    cleaned = [t if t.strip() else " " for t in texts]
    if not cleaned:
        return np.zeros((0, 1), dtype=np.float64)
    try:
        vectorizer = TfidfVectorizer(max_features=4096, ngram_range=(1, 2), min_df=1)
        X = vectorizer.fit_transform(cleaned)
        if X.shape[1] == 0:
            return None
        dense = X.toarray().astype(np.float64)
        return normalize(dense, axis=1, norm="l2")
    except ValueError:
        return None


def embed_tfidf_char(texts: Sequence[str]) -> np.ndarray | None:
    """Character n-gram TF-IDF fallback when word vocab is empty."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize

    cleaned = [t if t.strip() else " " for t in texts]
    if not cleaned:
        return np.zeros((0, 1), dtype=np.float64)
    try:
        vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            max_features=4096,
            min_df=1,
        )
        X = vectorizer.fit_transform(cleaned)
        if X.shape[1] == 0:
            return None
        dense = X.toarray().astype(np.float64)
        return normalize(dense, axis=1, norm="l2")
    except ValueError:
        return None


class TopicShiftEmbedder:
    """
    Resolve one backend for the full transcript before any embed/cache.

    Transformer LRU keyed by (backend, model, preprocessing_version, text).
    TF-IDF paths never use cross-call vector cache.
    """

    def __init__(
        self,
        *,
        en_model: str = DEFAULT_EN_MODEL,
        multi_model: str = DEFAULT_MULTI_MODEL,
        batch_size: int = 32,
        allow_downloads: bool = True,
        lru_size: int = 4096,
    ) -> None:
        self.en_model = en_model
        self.multi_model = multi_model
        self.batch_size = max(1, int(batch_size))
        self.allow_downloads = bool(allow_downloads)
        self.lru_size = max(0, int(lru_size))
        self._cache: dict[tuple[str, str, str, str], np.ndarray] = {}
        self._cache_order: list[tuple[str, str, str, str]] = []

    def _cache_get(
        self, backend: str, model: str, text: str
    ) -> np.ndarray | None:
        key = (backend, model, PREPROCESSING_VERSION, text)
        vec = self._cache.get(key)
        if vec is None:
            return None
        return vec.copy()

    def _cache_put(
        self, backend: str, model: str, text: str, vec: np.ndarray
    ) -> None:
        if self.lru_size <= 0:
            return
        key = (backend, model, PREPROCESSING_VERSION, text)
        self._cache[key] = vec.copy()
        self._cache_order.append(key)
        while len(self._cache_order) > self.lru_size:
            old = self._cache_order.pop(0)
            self._cache.pop(old, None)

    def _try_transformers(
        self, texts: Sequence[str], *, backend: BackendId, model_name: str
    ) -> np.ndarray | None:
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except Exception:
            return None

        # Local-only when downloads disabled
        local_only = not self.allow_downloads
        try:
            tokenizer = AutoTokenizer.from_pretrained(
                model_name, local_files_only=local_only
            )
            model = AutoModel.from_pretrained(model_name, local_files_only=local_only)
        except Exception:
            return None

        model.eval()
        device = torch.device("cpu")
        model.to(device)

        out_rows: list[np.ndarray] = []
        # Deduplicate for embedding, map back
        unique: list[str] = []
        index_of: dict[str, int] = {}
        for t in texts:
            if t not in index_of:
                index_of[t] = len(unique)
                unique.append(t)

        unique_vecs: list[np.ndarray | None] = [None] * len(unique)
        pending_idx: list[int] = []
        pending_texts: list[str] = []
        for ui, ut in enumerate(unique):
            cached = self._cache_get(backend, model_name, ut)
            if cached is not None:
                unique_vecs[ui] = cached
            else:
                pending_idx.append(ui)
                pending_texts.append(ut)

        try:
            for start in range(0, len(pending_texts), self.batch_size):
                batch = pending_texts[start : start + self.batch_size]
                encoded = tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=256,
                    return_tensors="pt",
                )
                encoded = {k: v.to(device) for k, v in encoded.items()}
                with torch.no_grad():
                    outputs = model(**encoded)
                    hidden = outputs.last_hidden_state
                    mask = encoded["attention_mask"].unsqueeze(-1).float()
                    summed = (hidden * mask).sum(dim=1)
                    counts = mask.sum(dim=1).clamp(min=1e-6)
                    pooled = (summed / counts).cpu().numpy().astype(np.float64)
                pooled = _l2_normalize(pooled)
                for j, row in enumerate(pooled):
                    ui = pending_idx[start + j]
                    unique_vecs[ui] = row
                    self._cache_put(backend, model_name, pending_texts[start + j], row)
        except Exception:
            return None

        if any(v is None for v in unique_vecs):
            return None
        for t in texts:
            out_rows.append(unique_vecs[index_of[t]])  # type: ignore[arg-type]
        return np.stack(out_rows, axis=0)

    def embed(
        self,
        texts: Sequence[str],
        *,
        backend: BackendId,
        semantics_version: str,
    ) -> EmbedResult | None:
        texts = list(texts)
        if backend in ("transformers_en", "transformers_multi"):
            model_name = (
                self.en_model if backend == "transformers_en" else self.multi_model
            )
            vectors = self._try_transformers(texts, backend=backend, model_name=model_name)
            if vectors is not None:
                return EmbedResult(
                    backend=backend,
                    model_name=model_name,
                    vectors=vectors,
                    semantics_version=semantics_version,
                    used_fallback=False,
                    fallback_reason=None,
                )
            # Full-corpus restart via TF-IDF (caller may choose word then char)
            return None

        if backend == "tfidf":
            vectors = embed_tfidf_word(texts)
            if vectors is None:
                return None
            return EmbedResult(
                backend="tfidf",
                model_name=None,
                vectors=vectors,
                semantics_version=semantics_version,
                used_fallback=False,
                fallback_reason=None,
            )

        if backend == "tfidf_char":
            vectors = embed_tfidf_char(texts)
            if vectors is None:
                return None
            return EmbedResult(
                backend="tfidf_char",
                model_name=None,
                vectors=vectors,
                semantics_version=semantics_version,
                used_fallback=False,
                fallback_reason=None,
            )
        return None
