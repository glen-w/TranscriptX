"""
Embedding generation and caching utilities.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

from transcriptx.core.utils.logger import log_warning
from transcriptx.core.utils.nlp_utils import preprocess_for_similarity


class EmbeddingCache:
    """Simple embedding cache keyed by preprocessed text."""

    def __init__(self) -> None:
        self._cache: Dict[str, np.ndarray] = {}

    def get(self, key: str) -> Optional[np.ndarray]:
        return self._cache.get(key)

    def set(self, key: str, value: np.ndarray) -> None:
        self._cache[key] = value


def get_text_embedding(
    text: str,
    model: Any,
    tokenizer: Any,
    device: Any,
    torch_module: Any,
    cache: EmbeddingCache,
    log_tag: str,
) -> Optional[np.ndarray]:
    """Generate embedding for a text, with caching and preprocessing."""
    if not model or not tokenizer:
        return None

    try:
        preprocessed_text = preprocess_for_similarity(text)
        if not preprocessed_text:
            return None

        cached = cache.get(preprocessed_text)
        if cached is not None:
            return cached

        inputs = tokenizer(
            preprocessed_text,
            return_tensors="pt",
            max_length=512,
            truncation=True,
            padding=True,
        ).to(device)

        with torch_module.no_grad():
            outputs = model(**inputs)
            embeddings = outputs.last_hidden_state.mean(dim=1)
            result = embeddings.cpu().numpy()

        cache.set(preprocessed_text, result)
        return result
    except Exception as exc:
        log_warning(log_tag, f"Failed to get embedding for text: {exc}")
        return None
