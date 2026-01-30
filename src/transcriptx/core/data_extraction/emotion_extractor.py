"""
Emotion data extractor for TranscriptX.

This module provides the EmotionDataExtractor class that extracts speaker-level
emotion data from analysis results and transforms it for database storage.
"""

import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from .base_extractor import BaseDataExtractor
from .validation import DataValidationError, validate_emotion_data

logger = logging.getLogger(__name__)


class EmotionDataExtractor(BaseDataExtractor):
    """
    Emotion data extractor for speaker-level emotion analysis.

    This extractor processes emotion analysis results and extracts speaker-specific
    emotion data including dominant emotions, distribution, stability, and transitions.
    """

    def extract_speaker_data(
        self, analysis_results: Dict[str, Any], speaker_id: int
    ) -> Dict[str, Any]:
        """
        Extract speaker-level emotion data from analysis results.

        Args:
            analysis_results: Complete analysis results for the conversation
            speaker_id: ID of the speaker to extract data for

        Returns:
            Dictionary containing extracted emotion data

        Raises:
            ValueError: If required data is missing or invalid
            DataValidationError: If extracted data fails validation
        """
        self.logger.info(f"Extracting emotion data for speaker {speaker_id}")

        # Get speaker segments
        speaker_segments = self.get_speaker_segments(analysis_results, speaker_id)

        if not speaker_segments:
            self.logger.warning(f"No segments found for speaker {speaker_id}")
            return self._create_empty_emotion_data()

        # Extract emotion data
        all_emotions = []
        emotion_scores_list = []
        dominant_emotions = []

        for segment in speaker_segments:
            # Extract dominant emotion
            dominant_emotion = segment.get("dominant_emotion")
            if dominant_emotion:
                dominant_emotions.append(dominant_emotion)
                all_emotions.append(dominant_emotion)

            # Extract emotion scores
            emotion_scores = segment.get("emotion_scores", {})
            if isinstance(emotion_scores, dict):
                emotion_scores_list.append(emotion_scores)

        # Calculate emotion metrics
        dominant_emotion = self.get_most_frequent(dominant_emotions)
        emotion_distribution = self._calculate_emotion_distribution(dominant_emotions)
        emotional_stability = self._calculate_emotional_stability(emotion_scores_list)
        emotion_transition_patterns = self._calculate_transition_patterns(
            dominant_emotions
        )
        emotional_reactivity = self._calculate_emotional_reactivity(emotion_scores_list)
        emotion_consistency = self._calculate_emotion_consistency(dominant_emotions)

        # Create emotion data
        emotion_data = {
            "dominant_emotion": dominant_emotion,
            "emotion_distribution": emotion_distribution,
            "emotional_stability": emotional_stability,
            "emotion_transition_patterns": emotion_transition_patterns,
            "emotional_reactivity": emotional_reactivity,
            "emotion_consistency": emotion_consistency,
        }

        self.logger.info(
            f"Extracted emotion data for speaker {speaker_id}: "
            f"dominant='{dominant_emotion}', "
            f"stability={emotional_stability}, "
            f"reactivity={emotional_reactivity}"
        )

        return emotion_data

    def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate extracted emotion data.

        Args:
            data: Extracted emotion data to validate

        Returns:
            True if data is valid

        Raises:
            DataValidationError: If data fails validation
        """
        try:
            return validate_emotion_data(data)
        except DataValidationError as e:
            self.logger.error(f"Emotion data validation failed: {e.message}")
            raise

    def transform_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform emotion data for database storage.

        Args:
            data: Raw extracted emotion data

        Returns:
            Transformed data ready for database storage
        """
        # Ensure all required fields are present
        transformed_data = {
            "dominant_emotion": data.get("dominant_emotion"),
            "emotion_distribution": data.get("emotion_distribution", {}),
            "emotional_stability": data.get("emotional_stability"),
            "emotion_transition_patterns": data.get("emotion_transition_patterns", {}),
            "emotional_reactivity": data.get("emotional_reactivity"),
            "emotion_consistency": data.get("emotion_consistency"),
        }

        return transformed_data

    def _create_empty_emotion_data(self) -> Dict[str, Any]:
        """
        Create empty emotion data structure.

        Returns:
            Empty emotion data structure
        """
        return {
            "dominant_emotion": None,
            "emotion_distribution": {},
            "emotional_stability": None,
            "emotion_transition_patterns": {},
            "emotional_reactivity": None,
            "emotion_consistency": None,
        }

    def _calculate_emotion_distribution(
        self, dominant_emotions: List[str]
    ) -> Dict[str, float]:
        """
        Calculate distribution of emotions.

        Args:
            dominant_emotions: List of dominant emotions

        Returns:
            Dictionary mapping emotions to their frequencies
        """
        if not dominant_emotions:
            return {}

        counter = Counter(dominant_emotions)
        total = len(dominant_emotions)

        distribution = {}
        for emotion, count in counter.items():
            distribution[emotion] = count / total

        return distribution

    def _calculate_emotional_stability(
        self, emotion_scores_list: List[Dict[str, float]]
    ) -> Optional[float]:
        """
        Calculate emotional stability score.

        Args:
            emotion_scores_list: List of emotion score dictionaries

        Returns:
            Stability score between 0 and 1, or None if insufficient data
        """
        if len(emotion_scores_list) < 2:
            return None

        # Calculate variance in emotion scores across segments
        all_scores = []
        for scores in emotion_scores_list:
            all_scores.extend(scores.values())

        if not all_scores:
            return None

        # Calculate coefficient of variation (lower = more stable)
        mean_score = sum(all_scores) / len(all_scores)
        if mean_score == 0:
            return None

        variance = sum((score - mean_score) ** 2 for score in all_scores) / len(
            all_scores
        )
        std_dev = variance**0.5
        coefficient_of_variation = std_dev / abs(mean_score)

        # Convert to stability score (0-1, higher = more stable)
        stability_score = max(0.0, 1.0 - min(coefficient_of_variation, 1.0))

        return stability_score

    def _calculate_transition_patterns(
        self, dominant_emotions: List[str]
    ) -> Dict[str, Any]:
        """
        Calculate emotion transition patterns.

        Args:
            dominant_emotions: List of dominant emotions in order

        Returns:
            Dictionary containing transition patterns
        """
        if len(dominant_emotions) < 2:
            return {}

        # Count transitions between emotions
        transitions = {}
        for i in range(len(dominant_emotions) - 1):
            current_emotion = dominant_emotions[i]
            next_emotion = dominant_emotions[i + 1]

            if current_emotion not in transitions:
                transitions[current_emotion] = {}

            if next_emotion not in transitions[current_emotion]:
                transitions[current_emotion][next_emotion] = 0

            transitions[current_emotion][next_emotion] += 1

        # Calculate transition probabilities
        transition_probabilities = {}
        for emotion, next_emotions in transitions.items():
            total_transitions = sum(next_emotions.values())
            transition_probabilities[emotion] = {
                next_emotion: count / total_transitions
                for next_emotion, count in next_emotions.items()
            }

        return {
            "transitions": transitions,
            "transition_probabilities": transition_probabilities,
            "total_transitions": len(dominant_emotions) - 1,
        }

    def _calculate_emotional_reactivity(
        self, emotion_scores_list: List[Dict[str, float]]
    ) -> Optional[float]:
        """
        Calculate emotional reactivity score.

        Args:
            emotion_scores_list: List of emotion score dictionaries

        Returns:
            Reactivity score between 0 and 1, or None if insufficient data
        """
        if len(emotion_scores_list) < 2:
            return None

        # Calculate how quickly emotions change between segments
        reactivity_scores = []

        for i in range(len(emotion_scores_list) - 1):
            current_scores = emotion_scores_list[i]
            next_scores = emotion_scores_list[i + 1]

            # Calculate difference in emotion scores
            total_diff = 0
            count = 0

            for emotion in set(current_scores.keys()) | set(next_scores.keys()):
                current_score = current_scores.get(emotion, 0)
                next_score = next_scores.get(emotion, 0)
                diff = abs(next_score - current_score)
                total_diff += diff
                count += 1

            if count > 0:
                avg_diff = total_diff / count
                reactivity_scores.append(avg_diff)

        if not reactivity_scores:
            return None

        # Calculate average reactivity
        avg_reactivity = sum(reactivity_scores) / len(reactivity_scores)

        # Normalize to 0-1 range (higher = more reactive)
        max_reactivity = 2.0  # Maximum expected reactivity
        normalized_reactivity = min(1.0, avg_reactivity / max_reactivity)

        return normalized_reactivity

    def _calculate_emotion_consistency(
        self, dominant_emotions: List[str]
    ) -> Optional[float]:
        """
        Calculate emotion consistency score.

        Args:
            dominant_emotions: List of dominant emotions

        Returns:
            Consistency score between 0 and 1, or None if insufficient data
        """
        if len(dominant_emotions) < 2:
            return None

        # Calculate how consistent the dominant emotion is
        counter = Counter(dominant_emotions)
        most_common_emotion = counter.most_common(1)[0][0]
        most_common_count = counter[most_common_emotion]

        # Consistency is the proportion of the most common emotion
        consistency_score = most_common_count / len(dominant_emotions)

        return consistency_score
