"""
Topic data extractor for TranscriptX.

This module provides the TopicDataExtractor class that extracts speaker-level
topic modeling data from analysis results and transforms it for database storage.
"""

import logging
from typing import Any, Dict, List

from .base_extractor import BaseDataExtractor
from .validation import DataValidationError, validate_topic_data

logger = logging.getLogger(__name__)


class TopicDataExtractor(BaseDataExtractor):
    """
    Topic data extractor for speaker-level topic modeling analysis.

    This extractor processes topic modeling results and extracts speaker-specific
    topic data including preferred topics, expertise scores, and engagement patterns.
    """

    def __init__(self):
        super().__init__("topic_modeling")

    def extract_data(
        self, analysis_results: Dict[str, Any], speaker_id: str
    ) -> Dict[str, Any]:
        try:
            speaker_id_int = int(speaker_id)
        except Exception:
            speaker_id_int = speaker_id  # type: ignore[assignment]
        return self.extract_speaker_data(analysis_results, speaker_id=speaker_id_int)  # type: ignore[arg-type]

    def extract_speaker_data(
        self, analysis_results: Dict[str, Any], speaker_id: int | str
    ) -> Dict[str, Any]:
        """
        Extract speaker-level topic data from analysis results.

        Args:
            analysis_results: Complete analysis results for the conversation
            speaker_id: ID of the speaker to extract data for

        Returns:
            Dictionary containing extracted topic data

        Raises:
            ValueError: If required data is missing or invalid
            DataValidationError: If extracted data fails validation
        """
        self.logger.info(f"Extracting topic data for speaker {speaker_id}")

        # Get speaker segments
        speaker_segments = self.get_speaker_segments(analysis_results, speaker_id)

        if not speaker_segments:
            self.logger.warning(f"No segments found for speaker {speaker_id}")
            return self._create_empty_topic_data()

        # Extract topic data
        topic_contributions = {}
        topic_engagement = []

        for segment in speaker_segments:
            # Extract topic assignments
            topic_id = segment.get("topic_id")
            topic_confidence = self.safe_float(segment.get("topic_confidence"))

            if topic_id is not None:
                if topic_id not in topic_contributions:
                    topic_contributions[topic_id] = {
                        "count": 0,
                        "total_confidence": 0.0,
                        "segments": [],
                    }

                topic_contributions[topic_id]["count"] += 1
                topic_contributions[topic_id]["total_confidence"] += (
                    topic_confidence or 0.0
                )
                topic_contributions[topic_id]["segments"].append(segment)

        # Calculate topic metrics
        preferred_topics = self._calculate_preferred_topics(topic_contributions)
        topic_expertise_scores = self._calculate_expertise_scores(topic_contributions)
        topic_contribution_patterns = self._calculate_contribution_patterns(
            topic_contributions
        )
        topic_engagement_style = self._determine_engagement_style(topic_contributions)
        topic_evolution_trends = self._calculate_evolution_trends(speaker_segments)

        # Create topic data
        topic_data = {
            "preferred_topics": preferred_topics,
            "topic_expertise_scores": topic_expertise_scores,
            "topic_contribution_patterns": topic_contribution_patterns,
            "topic_engagement_style": topic_engagement_style,
            "topic_evolution_trends": topic_evolution_trends,
        }

        self.logger.info(
            f"Extracted topic data for speaker {speaker_id}: "
            f"preferred_topics={len(preferred_topics)}, "
            f"engagement_style='{topic_engagement_style}'"
        )

        return topic_data

    def validate_data(
        self, data: Dict[str, Any], speaker_id: str | None = None
    ) -> bool:
        """
        Validate extracted topic data.

        Args:
            data: Extracted topic data to validate

        Returns:
            True if data is valid

        Raises:
            DataValidationError: If data fails validation
        """
        try:
            return validate_topic_data(data)
        except DataValidationError as e:
            self.logger.error(f"Topic data validation failed: {e.message}")
            raise

    def transform_data(
        self, data: Dict[str, Any], speaker_id: str | None = None
    ) -> Dict[str, Any]:
        """
        Transform topic data for database storage.

        Args:
            data: Raw extracted topic data

        Returns:
            Transformed data ready for database storage
        """
        # Ensure all required fields are present
        transformed_data = {
            "preferred_topics": data.get("preferred_topics", {}),
            "topic_expertise_scores": data.get("topic_expertise_scores", {}),
            "topic_contribution_patterns": data.get("topic_contribution_patterns", {}),
            "topic_engagement_style": data.get("topic_engagement_style"),
            "topic_evolution_trends": data.get("topic_evolution_trends", {}),
        }

        return transformed_data

    def _create_empty_topic_data(self) -> Dict[str, Any]:
        """
        Create empty topic data structure.

        Returns:
            Empty topic data structure
        """
        return {
            "preferred_topics": {},
            "topic_expertise_scores": {},
            "topic_contribution_patterns": {},
            "topic_engagement_style": None,
            "topic_evolution_trends": {},
        }

    def _calculate_preferred_topics(
        self, topic_contributions: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Calculate preferred topics based on contribution frequency.

        Args:
            topic_contributions: Dictionary of topic contributions

        Returns:
            Dictionary mapping topic IDs to preference scores
        """
        if not topic_contributions:
            return {}

        total_segments = sum(
            contrib["count"] for contrib in topic_contributions.values()
        )

        preferred_topics = {}
        for topic_id, contrib in topic_contributions.items():
            preference_score = contrib["count"] / total_segments
            preferred_topics[str(topic_id)] = preference_score

        return preferred_topics

    def _calculate_expertise_scores(
        self, topic_contributions: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Calculate expertise scores for topics.

        Args:
            topic_contributions: Dictionary of topic contributions

        Returns:
            Dictionary mapping topic IDs to expertise scores
        """
        if not topic_contributions:
            return {}

        expertise_scores = {}
        for topic_id, contrib in topic_contributions.items():
            if contrib["count"] > 0:
                avg_confidence = contrib["total_confidence"] / contrib["count"]
                expertise_scores[str(topic_id)] = avg_confidence
            else:
                expertise_scores[str(topic_id)] = 0.0

        return expertise_scores

    def _calculate_contribution_patterns(
        self, topic_contributions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate topic contribution patterns.

        Args:
            topic_contributions: Dictionary of topic contributions

        Returns:
            Dictionary containing contribution patterns
        """
        if not topic_contributions:
            return {}

        patterns = {
            "topic_frequency": {},
            "average_confidence": {},
            "contribution_timing": {},
        }

        for topic_id, contrib in topic_contributions.items():
            patterns["topic_frequency"][str(topic_id)] = contrib["count"]

            if contrib["count"] > 0:
                patterns["average_confidence"][str(topic_id)] = (
                    contrib["total_confidence"] / contrib["count"]
                )
            else:
                patterns["average_confidence"][str(topic_id)] = 0.0

        return patterns

    def _determine_engagement_style(self, topic_contributions: Dict[str, Any]) -> str:
        """
        Determine the speaker's topic engagement style.

        Args:
            topic_contributions: Dictionary of topic contributions

        Returns:
            Engagement style string
        """
        if not topic_contributions:
            return "passive"

        # Calculate engagement metrics
        total_topics = len(topic_contributions)
        total_contributions = sum(
            contrib["count"] for contrib in topic_contributions.values()
        )

        if total_contributions == 0:
            return "passive"

        # Calculate diversity and intensity
        topic_diversity = total_topics / max(total_contributions, 1)
        avg_confidence = (
            sum(contrib["total_confidence"] for contrib in topic_contributions.values())
            / total_contributions
        )

        # Determine style based on metrics
        if topic_diversity > 0.5 and avg_confidence > 0.7:
            return "expert"
        elif topic_diversity > 0.3 and avg_confidence > 0.5:
            return "engaged"
        elif avg_confidence > 0.6:
            return "focused"
        else:
            return "passive"

    def _calculate_evolution_trends(
        self, speaker_segments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate topic evolution trends over time.

        Args:
            speaker_segments: List of speaker segments

        Returns:
            Dictionary containing evolution trends
        """
        if len(speaker_segments) < 2:
            return {}

        # Sort segments by timestamp
        sorted_segments = sorted(speaker_segments, key=lambda x: x.get("start_time", 0))

        # Track topic changes over time
        topic_sequence = []
        for segment in sorted_segments:
            topic_id = segment.get("topic_id")
            if topic_id is not None:
                topic_sequence.append(topic_id)

        # Calculate evolution metrics
        unique_topics = len(set(topic_sequence))
        topic_changes = sum(
            1
            for i in range(len(topic_sequence) - 1)
            if topic_sequence[i] != topic_sequence[i + 1]
        )

        evolution_rate = topic_changes / max(len(topic_sequence) - 1, 1)

        return {
            "unique_topics": unique_topics,
            "topic_changes": topic_changes,
            "evolution_rate": evolution_rate,
            "topic_sequence": topic_sequence,
        }
