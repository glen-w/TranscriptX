"""
Semantic similarity calculations with transformer and TF-IDF fallback.
"""

from __future__ import annotations

from typing import Any

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import log_warning
from transcriptx.core.utils.nlp_utils import preprocess_for_similarity

from .embeddings import EmbeddingCache, get_text_embedding


class SemanticSimilarityCalculator:
    """Calculate semantic similarity with transformer embeddings and TF-IDF fallback."""

    def __init__(
        self,
        model_manager: Any,
        embedding_cache: EmbeddingCache,
        log_tag: str,
    ) -> None:
        self.model_manager = model_manager
        self.embedding_cache = embedding_cache
        self.log_tag = log_tag

    def calculate(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts."""
        if not self.model_manager.model or not self.model_manager.tokenizer:
            return self.tfidf_similarity(text1, text2)

        emb1 = get_text_embedding(
            text1,
            self.model_manager.model,
            self.model_manager.tokenizer,
            self.model_manager.device,
            self.model_manager.torch,
            self.embedding_cache,
            self.log_tag,
        )
        emb2 = get_text_embedding(
            text2,
            self.model_manager.model,
            self.model_manager.tokenizer,
            self.model_manager.device,
            self.model_manager.torch,
            self.embedding_cache,
            self.log_tag,
        )

        if emb1 is None or emb2 is None:
            return self.tfidf_similarity(text1, text2)

        from sklearn.metrics.pairwise import cosine_similarity

        similarity = cosine_similarity(emb1, emb2)[0][0]
        return float(similarity)

    def tfidf_similarity(self, text1: str, text2: str) -> float:
        """Calculate TF-IDF similarity as fallback."""
        try:
            preprocessed_text1 = preprocess_for_similarity(text1)
            preprocessed_text2 = preprocess_for_similarity(text2)

            if not preprocessed_text1 or not preprocessed_text2:
                return 0.0

            vector_config = get_config().analysis.vectorization
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            vectorizer = TfidfVectorizer(
                lowercase=True,
                stop_words="english",
                ngram_range=vector_config.ngram_range,
                max_features=vector_config.max_features,
            )

            tfidf_matrix = vectorizer.fit_transform(
                [preprocessed_text1, preprocessed_text2]
            )
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(similarity)
        except Exception as exc:
            log_warning(self.log_tag, f"TF-IDF similarity failed: {exc}")
            return 0.0
