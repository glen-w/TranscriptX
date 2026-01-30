"""
Sentiment data extractor for TranscriptX.

This module provides the SentimentDataExtractor class that extracts speaker-level
sentiment data from analysis results and transforms it for database storage.
"""

import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from .base_extractor import BaseDataExtractor
from .validation import DataValidationError, validate_sentiment_data

logger = logging.getLogger(__name__)


class SentimentDataExtractor(BaseDataExtractor):
    """
    Sentiment data extractor for speaker-level sentiment analysis.

    This extractor processes sentiment analysis results and extracts speaker-specific
    sentiment data including average scores, volatility, trends, and trigger words.
    """

    def extract_speaker_data(
        self, analysis_results: Dict[str, Any], speaker_id: int
    ) -> Dict[str, Any]:
        """
        Extract speaker-level sentiment data from analysis results.

        Args:
            analysis_results: Complete analysis results for the conversation
            speaker_id: ID of the speaker to extract data for

        Returns:
            Dictionary containing extracted sentiment data

        Raises:
            ValueError: If required data is missing or invalid
            DataValidationError: If extracted data fails validation
        """
        self.logger.info(f"Extracting sentiment data for speaker {speaker_id}")

        # Get speaker segments
        speaker_segments = self.get_speaker_segments(analysis_results, speaker_id)

        if not speaker_segments:
            self.logger.warning(f"No segments found for speaker {speaker_id}")
            return self._create_empty_sentiment_data()

        # Extract sentiment scores
        sentiment_scores = []
        sentiment_labels = []
        trigger_words = []

        for segment in speaker_segments:
            # Extract sentiment score
            sentiment_score = self.safe_float(segment.get("sentiment_score"))
            if sentiment_score is not None:
                sentiment_scores.append(sentiment_score)

            # Extract sentiment label
            sentiment_label = segment.get("sentiment_label")
            if sentiment_label:
                sentiment_labels.append(sentiment_label)

            # Extract trigger words
            segment_trigger_words = segment.get("trigger_words", [])
            if isinstance(segment_trigger_words, list):
                trigger_words.extend(segment_trigger_words)

        # Calculate sentiment metrics
        average_sentiment_score = self.calculate_average(sentiment_scores)
        sentiment_volatility = self.calculate_volatility(sentiment_scores)
        dominant_sentiment_pattern = self.get_most_frequent(sentiment_labels)

        # Analyze trigger words
        positive_trigger_words, negative_trigger_words = self._analyze_trigger_words(
            trigger_words, sentiment_scores
        )

        # Calculate sentiment trends
        sentiment_trends = self._calculate_sentiment_trends(speaker_segments)

        # Calculate consistency score
        sentiment_consistency_score = self._calculate_consistency_score(
            sentiment_scores
        )

        # Create sentiment data
        sentiment_data = {
            "average_sentiment_score": average_sentiment_score,
            "sentiment_volatility": sentiment_volatility,
            "dominant_sentiment_pattern": dominant_sentiment_pattern,
            "sentiment_trends": sentiment_trends,
            "positive_trigger_words": positive_trigger_words,
            "negative_trigger_words": negative_trigger_words,
            "sentiment_consistency_score": sentiment_consistency_score,
        }

        self.logger.info(
            f"Extracted sentiment data for speaker {speaker_id}: "
            f"avg_score={average_sentiment_score}, "
            f"volatility={sentiment_volatility}, "
            f"dominant_pattern={dominant_sentiment_pattern}"
        )

        return sentiment_data

    def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate extracted sentiment data.

        Args:
            data: Extracted sentiment data to validate

        Returns:
            True if data is valid

        Raises:
            DataValidationError: If data fails validation
        """
        try:
            return validate_sentiment_data(data)
        except DataValidationError as e:
            self.logger.error(f"Sentiment data validation failed: {e.message}")
            raise

    def transform_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform sentiment data for database storage.

        Args:
            data: Raw extracted sentiment data

        Returns:
            Transformed data ready for database storage
        """
        # Ensure all required fields are present
        transformed_data = {
            "average_sentiment_score": data.get("average_sentiment_score"),
            "sentiment_volatility": data.get("sentiment_volatility"),
            "dominant_sentiment_pattern": data.get("dominant_sentiment_pattern"),
            "sentiment_trends": data.get("sentiment_trends", {}),
            "positive_trigger_words": data.get("positive_trigger_words", []),
            "negative_trigger_words": data.get("negative_trigger_words", []),
            "sentiment_consistency_score": data.get("sentiment_consistency_score"),
        }

        return transformed_data

    def _create_empty_sentiment_data(self) -> Dict[str, Any]:
        """
        Create empty sentiment data structure.

        Returns:
            Empty sentiment data structure
        """
        return {
            "average_sentiment_score": None,
            "sentiment_volatility": None,
            "dominant_sentiment_pattern": None,
            "sentiment_trends": {},
            "positive_trigger_words": [],
            "negative_trigger_words": [],
            "sentiment_consistency_score": None,
        }

    def _analyze_trigger_words(
        self, trigger_words: List[str], sentiment_scores: List[float]
    ) -> tuple[List[str], List[str]]:
        """
        Analyze trigger words and categorize them by sentiment.

        Args:
            trigger_words: List of trigger words
            sentiment_scores: List of corresponding sentiment scores

        Returns:
            Tuple of (positive_trigger_words, negative_trigger_words)
        """
        if not trigger_words or not sentiment_scores:
            return [], []

        # Create word-sentiment mapping
        word_sentiment_map = {}
        for i, word in enumerate(trigger_words):
            if i < len(sentiment_scores):
                word_sentiment_map[word] = sentiment_scores[i]

        # Categorize words by sentiment
        positive_words = []
        negative_words = []

        for word, score in word_sentiment_map.items():
            if score > 0.1:  # Positive threshold
                positive_words.append(word)
            elif score < -0.1:  # Negative threshold
                negative_words.append(word)

        # Get most frequent words in each category
        positive_counter = Counter(positive_words)
        negative_counter = Counter(negative_words)

        positive_trigger_words = [word for word, _ in positive_counter.most_common(10)]
        negative_trigger_words = [word for word, _ in negative_counter.most_common(10)]

        return positive_trigger_words, negative_trigger_words

    def _calculate_sentiment_trends(
        self, speaker_segments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate sentiment trends over time.

        Args:
            speaker_segments: List of speaker segments

        Returns:
            Dictionary containing sentiment trends
        """
        if not speaker_segments:
            return {}

        # Sort segments by timestamp if available
        sorted_segments = sorted(speaker_segments, key=lambda x: x.get("start_time", 0))

        # Calculate moving average
        window_size = min(5, len(sorted_segments))
        moving_averages = []

        for i in range(len(sorted_segments) - window_size + 1):
            window_scores = []
            for j in range(window_size):
                score = self.safe_float(sorted_segments[i + j].get("sentiment_score"))
                if score is not None:
                    window_scores.append(score)

            if window_scores:
                moving_averages.append(sum(window_scores) / len(window_scores))

        # Calculate trend direction
        trend_direction = "stable"
        if len(moving_averages) >= 2:
            first_half = moving_averages[: len(moving_averages) // 2]
            second_half = moving_averages[len(moving_averages) // 2 :]

            if first_half and second_half:
                first_avg = sum(first_half) / len(first_half)
                second_avg = sum(second_half) / len(second_half)

                if second_avg > first_avg + 0.1:
                    trend_direction = "improving"
                elif second_avg < first_avg - 0.1:
                    trend_direction = "declining"

        return {
            "trend_direction": trend_direction,
            "moving_averages": moving_averages,
            "segment_count": len(sorted_segments),
            "trend_confidence": len(moving_averages) / max(len(sorted_segments), 1),
        }

    def _calculate_consistency_score(
        self, sentiment_scores: List[float]
    ) -> Optional[float]:
        """
        Calculate sentiment consistency score.

        Args:
            sentiment_scores: List of sentiment scores

        Returns:
            Consistency score between 0 and 1, or None if insufficient data
        """
        if len(sentiment_scores) < 2:
            return None

        # Calculate how consistent the sentiment scores are
        # Lower volatility means higher consistency
        volatility = self.calculate_volatility(sentiment_scores)
        if volatility is None:
            return None

        # Convert volatility to consistency score (0-1)
        # Lower volatility = higher consistency
        max_volatility = 2.0  # Maximum expected volatility for sentiment scores
        consistency_score = max(0.0, 1.0 - (volatility / max_volatility))

        return consistency_score
