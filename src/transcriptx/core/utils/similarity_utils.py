"""
Shared similarity calculation utilities for TranscriptX.

This module provides centralized similarity calculation functions that are used
across multiple analysis modules to eliminate code duplication and ensure
consistent similarity metrics throughout the codebase.
"""

import re
from collections import Counter
from typing import Any, Dict, List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from transcriptx.core.utils.logger import get_logger

logger = get_logger()


class SimilarityCalculator:
    """
    Centralized similarity calculation utility.

    This class provides various similarity calculation methods that can be used
    across different analysis modules to ensure consistency and eliminate duplication.
    """

    def __init__(self):
        """Initialize the similarity calculator."""
        self.tfidf_vectorizer = None
        self._initialize_tfidf()

    def _initialize_tfidf(self):
        """Initialize TF-IDF vectorizer for text similarity."""
        try:
            from transcriptx.core.utils.config import get_config

            vector_config = get_config().analysis.vectorization
            self.tfidf_vectorizer = TfidfVectorizer(
                lowercase=True,
                stop_words="english",
                ngram_range=vector_config.ngram_range,
                max_features=vector_config.max_features,
                min_df=vector_config.min_df,
                max_df=vector_config.max_df,
            )
        except Exception as e:
            logger.warning(f"Failed to initialize TF-IDF vectorizer: {e}")
            self.tfidf_vectorizer = None

    def calculate_text_similarity(
        self, text1: str, text2: str, method: str = "tfidf"
    ) -> float:
        """
        Calculate similarity between two text strings.

        Args:
            text1: First text string
            text2: Second text string
            method: Similarity method ('tfidf', 'jaccard', 'cosine', 'overlap')

        Returns:
            Similarity score between 0 and 1
        """
        if not text1 or not text2:
            return 0.0

        text1 = text1.strip()
        text2 = text2.strip()

        if text1 == text2:
            return 1.0

        if method == "tfidf":
            return self._tfidf_similarity(text1, text2)
        elif method == "jaccard":
            return self._jaccard_similarity(text1, text2)
        elif method == "cosine":
            return self._cosine_similarity(text1, text2)
        elif method == "overlap":
            return self._overlap_similarity(text1, text2)
        else:
            logger.warning(f"Unknown similarity method: {method}, using TF-IDF")
            return self._tfidf_similarity(text1, text2)

    def _tfidf_similarity(self, text1: str, text2: str) -> float:
        """Calculate TF-IDF based similarity."""
        try:
            if not self.tfidf_vectorizer:
                return self._jaccard_similarity(text1, text2)

            # Fit and transform both texts
            tfidf_matrix = self.tfidf_vectorizer.fit_transform([text1, text2])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(similarity)
        except Exception as e:
            logger.warning(f"TF-IDF similarity failed: {e}, falling back to Jaccard")
            return self._jaccard_similarity(text1, text2)

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """Calculate Jaccard similarity between two texts."""
        try:
            # Tokenize and create word sets
            words1 = set(self._tokenize_text(text1))
            words2 = set(self._tokenize_text(text2))

            if not words1 or not words2:
                return 0.0

            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))

            return intersection / union if union > 0 else 0.0
        except Exception as e:
            logger.warning(f"Jaccard similarity failed: {e}")
            return 0.0

    def _cosine_similarity(self, text1: str, text2: str) -> float:
        """Calculate cosine similarity between two texts."""
        try:
            words1 = self._tokenize_text(text1)
            words2 = self._tokenize_text(text2)

            # Create word frequency vectors
            all_words = set(words1 + words2)
            if not all_words:
                return 0.0

            vec1 = [words1.count(word) for word in all_words]
            vec2 = [words2.count(word) for word in all_words]

            # Calculate cosine similarity
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            norm1 = sum(a * a for a in vec1) ** 0.5
            norm2 = sum(b * b for b in vec2) ** 0.5

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return dot_product / (norm1 * norm2)
        except Exception as e:
            logger.warning(f"Cosine similarity failed: {e}")
            return 0.0

    def _overlap_similarity(self, text1: str, text2: str) -> float:
        """Calculate overlap similarity between two texts."""
        try:
            words1 = set(self._tokenize_text(text1))
            words2 = set(self._tokenize_text(text2))

            if not words1 or not words2:
                return 0.0

            intersection = len(words1.intersection(words2))
            min_length = min(len(words1), len(words2))

            return intersection / min_length if min_length > 0 else 0.0
        except Exception as e:
            logger.warning(f"Overlap similarity failed: {e}")
            return 0.0

    def _tokenize_text(self, text: str) -> List[str]:
        """Tokenize text into words."""
        # Remove punctuation and split into words
        words = re.findall(r"\b\w+\b", text.lower())
        # Filter out very short words
        return [word for word in words if len(word) > 2]

    def calculate_dict_similarity(
        self, dict1: Dict[str, Any], dict2: Dict[str, Any], method: str = "weighted"
    ) -> float:
        """
        Calculate similarity between two dictionaries.

        Args:
            dict1: First dictionary
            dict2: Second dictionary
            method: Similarity method ('weighted', 'jaccard', 'cosine')

        Returns:
            Similarity score between 0 and 1
        """
        if not dict1 or not dict2:
            return 0.0

        if method == "weighted":
            return self._weighted_dict_similarity(dict1, dict2)
        elif method == "jaccard":
            return self._jaccard_dict_similarity(dict1, dict2)
        elif method == "cosine":
            return self._cosine_dict_similarity(dict1, dict2)
        else:
            logger.warning(f"Unknown dict similarity method: {method}, using weighted")
            return self._weighted_dict_similarity(dict1, dict2)

    def _weighted_dict_similarity(
        self, dict1: Dict[str, Any], dict2: Dict[str, Any]
    ) -> float:
        """Calculate weighted similarity between dictionaries."""
        try:
            all_keys = set(dict1.keys()) | set(dict2.keys())
            if not all_keys:
                return 0.0

            similarities = []
            for key in all_keys:
                val1 = dict1.get(key, 0)
                val2 = dict2.get(key, 0)

                if val1 == 0 and val2 == 0:
                    similarities.append(1.0)  # Both zero = similar
                elif val1 == 0 or val2 == 0:
                    similarities.append(0.0)  # One zero, one non-zero = different
                else:
                    # Calculate relative similarity
                    max_val = max(val1, val2)
                    similarity = min(val1, val2) / max_val
                    similarities.append(similarity)

            return np.mean(similarities) if similarities else 0.0
        except Exception as e:
            logger.warning(f"Weighted dict similarity failed: {e}")
            return 0.0

    def _jaccard_dict_similarity(
        self, dict1: Dict[str, Any], dict2: Dict[str, Any]
    ) -> float:
        """Calculate Jaccard similarity between dictionary keys."""
        try:
            keys1 = set(dict1.keys())
            keys2 = set(dict2.keys())

            if not keys1 or not keys2:
                return 0.0

            intersection = len(keys1.intersection(keys2))
            union = len(keys1.union(keys2))

            return intersection / union if union > 0 else 0.0
        except Exception as e:
            logger.warning(f"Jaccard dict similarity failed: {e}")
            return 0.0

    def _cosine_dict_similarity(
        self, dict1: Dict[str, Any], dict2: Dict[str, Any]
    ) -> float:
        """Calculate cosine similarity between dictionary values."""
        try:
            all_keys = set(dict1.keys()) | set(dict2.keys())
            if not all_keys:
                return 0.0

            vec1 = [dict1.get(key, 0) for key in all_keys]
            vec2 = [dict2.get(key, 0) for key in all_keys]

            # Calculate cosine similarity
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            norm1 = sum(a * a for a in vec1) ** 0.5
            norm2 = sum(b * b for b in vec2) ** 0.5

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return dot_product / (norm1 * norm2)
        except Exception as e:
            logger.warning(f"Cosine dict similarity failed: {e}")
            return 0.0

    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two names.

        Args:
            name1: First name
            name2: Second name

        Returns:
            Similarity score between 0 and 1
        """
        if not name1 or not name2:
            return 0.0

        # Normalize names
        norm1 = self._normalize_name(name1)
        norm2 = self._normalize_name(name2)

        if norm1 == norm2:
            return 1.0

        # Calculate Jaccard similarity on words
        words1 = set(norm1.split())
        words2 = set(norm2.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0

    def _normalize_name(self, name: str) -> str:
        """Normalize a name for comparison."""
        # Remove extra whitespace and convert to lowercase
        normalized = re.sub(r"\s+", " ", name.strip().lower())
        # Remove common prefixes/suffixes
        normalized = re.sub(r"^(mr\.|mrs\.|ms\.|dr\.|prof\.)\s*", "", normalized)
        return normalized

    def calculate_behavioral_similarity(
        self, fingerprint1: Dict[str, Any], fingerprint2: Dict[str, Any]
    ) -> float:
        """
        Calculate similarity between two behavioral fingerprints.

        Args:
            fingerprint1: First behavioral fingerprint
            fingerprint2: Second behavioral fingerprint

        Returns:
            Similarity score between 0 and 1
        """
        try:
            similarities = []

            # Compare vocabulary patterns
            vocab1 = fingerprint1.get("vocabulary_patterns", {})
            vocab2 = fingerprint2.get("vocabulary_patterns", {})
            if vocab1 and vocab2:
                vocab_sim = self.calculate_dict_similarity(vocab1, vocab2)
                similarities.append(vocab_sim * 0.3)  # Weight: 30%

            # Compare speech patterns
            speech1 = fingerprint1.get("speech_patterns", {})
            speech2 = fingerprint2.get("speech_patterns", {})
            if speech1 and speech2:
                speech_sim = self._calculate_speech_similarity(speech1, speech2)
                similarities.append(speech_sim * 0.25)  # Weight: 25%

            # Compare emotion patterns
            emotion1 = fingerprint1.get("emotion_patterns", {})
            emotion2 = fingerprint2.get("emotion_patterns", {})
            if emotion1 and emotion2:
                emotion_sim = self.calculate_dict_similarity(emotion1, emotion2)
                similarities.append(emotion_sim * 0.25)  # Weight: 25%

            # Compare sentiment patterns
            sentiment1 = fingerprint1.get("sentiment_patterns", {})
            sentiment2 = fingerprint2.get("sentiment_patterns", {})
            if sentiment1 and sentiment2:
                sentiment_sim = self._calculate_sentiment_similarity(
                    sentiment1, sentiment2
                )
                similarities.append(sentiment_sim * 0.2)  # Weight: 20%

            return np.mean(similarities) if similarities else 0.0
        except Exception as e:
            logger.warning(f"Behavioral similarity calculation failed: {e}")
            return 0.0

    def _calculate_speech_similarity(
        self, speech1: Dict[str, Any], speech2: Dict[str, Any]
    ) -> float:
        """Calculate similarity between speech patterns."""
        try:
            similarities = []

            # Compare speaking rates
            rate1 = speech1.get("average_speaking_rate", 0)
            rate2 = speech2.get("average_speaking_rate", 0)
            if rate1 > 0 and rate2 > 0:
                rate_similarity = min(rate1, rate2) / max(rate1, rate2)
                similarities.append(rate_similarity)

            # Compare segment durations
            duration1 = speech1.get("average_segment_duration", 0)
            duration2 = speech2.get("average_segment_duration", 0)
            if duration1 > 0 and duration2 > 0:
                duration_similarity = min(duration1, duration2) / max(
                    duration1, duration2
                )
                similarities.append(duration_similarity)

            return np.mean(similarities) if similarities else 0.0
        except Exception as e:
            logger.warning(f"Speech similarity calculation failed: {e}")
            return 0.0

    def _calculate_sentiment_similarity(
        self, sentiment1: Dict[str, Any], sentiment2: Dict[str, Any]
    ) -> float:
        """Calculate similarity between sentiment patterns."""
        try:
            avg1 = sentiment1.get("average_sentiment", 0)
            avg2 = sentiment2.get("average_sentiment", 0)

            # Normalize to 0-1 range and calculate similarity
            normalized1 = (avg1 + 1) / 2  # Convert from [-1, 1] to [0, 1]
            normalized2 = (avg2 + 1) / 2

            return 1 - abs(normalized1 - normalized2)
        except Exception as e:
            logger.warning(f"Sentiment similarity calculation failed: {e}")
            return 0.0

    def extract_vocabulary_patterns(self, texts: List[str]) -> Dict[str, Any]:
        """
        Extract vocabulary patterns from a list of texts.

        Args:
            texts: List of text strings

        Returns:
            Dictionary containing vocabulary patterns
        """
        try:
            all_text = " ".join(texts)
            words = re.findall(r"\b\w+\b", all_text.lower())

            # Count word frequencies
            word_freq = Counter(words)

            # Filter out very short words and common stop words
            filtered_words = {
                word: freq
                for word, freq in word_freq.items()
                if len(word) > 2 and freq > 1
            }

            # Get most common words
            common_words = sorted(
                filtered_words.items(), key=lambda x: x[1], reverse=True
            )[:20]

            return {
                "common_words": [word for word, freq in common_words],
                "word_frequencies": dict(common_words),
                "total_words": len(words),
                "unique_words": len(filtered_words),
            }
        except Exception as e:
            logger.warning(f"Vocabulary pattern extraction failed: {e}")
            return {
                "common_words": [],
                "word_frequencies": {},
                "total_words": 0,
                "unique_words": 0,
            }


# Global instance for easy access
similarity_calculator = SimilarityCalculator()


# Convenience functions for backward compatibility
def calculate_text_similarity(text1: str, text2: str, method: str = "tfidf") -> float:
    """Calculate similarity between two text strings."""
    return similarity_calculator.calculate_text_similarity(text1, text2, method)


def calculate_dict_similarity(
    dict1: Dict[str, Any], dict2: Dict[str, Any], method: str = "weighted"
) -> float:
    """Calculate similarity between two dictionaries."""
    return similarity_calculator.calculate_dict_similarity(dict1, dict2, method)


def calculate_name_similarity(name1: str, name2: str) -> float:
    """Calculate similarity between two names."""
    return similarity_calculator.calculate_name_similarity(name1, name2)


def calculate_behavioral_similarity(
    fingerprint1: Dict[str, Any], fingerprint2: Dict[str, Any]
) -> float:
    """Calculate similarity between two behavioral fingerprints."""
    return similarity_calculator.calculate_behavioral_similarity(
        fingerprint1, fingerprint2
    )


def extract_vocabulary_patterns(texts: List[str]) -> Dict[str, Any]:
    """Extract vocabulary patterns from a list of texts."""
    return similarity_calculator.extract_vocabulary_patterns(texts)
