"""Performance data extractor for TranscriptX."""

import logging
from collections import Counter
from typing import Any, Dict, List

from .base_extractor import BaseDataExtractor
from .validation import DataValidationError, validate_performance_data

logger = logging.getLogger(__name__)


class PerformanceDataExtractor(BaseDataExtractor):
    """Performance data extractor for speaker-level performance analysis."""

    def extract_speaker_data(
        self, analysis_results: Dict[str, Any], speaker_id: int
    ) -> Dict[str, Any]:
        """Extract speaker-level performance data from analysis results."""
        self.logger.info(f"Extracting performance data for speaker {speaker_id}")

        speaker_segments = self.get_speaker_segments(analysis_results, speaker_id)

        if not speaker_segments:
            return self._create_empty_performance_data()

        # Extract performance data
        speaking_times = []
        word_counts = []
        participation_patterns = []

        for segment in speaker_segments:
            # Extract basic metrics
            speaking_time = segment.get("duration", 0.0)
            word_count = len(segment.get("text", "").split())

            speaking_times.append(speaking_time)
            word_counts.append(word_count)

            # Extract participation patterns
            participation = segment.get("participation", {})
            if participation:
                participation_patterns.append(participation)

        # Calculate performance metrics
        speaking_style = self._determine_speaking_style(speaking_times, word_counts)
        participation_patterns_data = self._analyze_participation_patterns(
            participation_patterns
        )
        performance_metrics = self._calculate_performance_metrics(
            speaking_times, word_counts
        )
        improvement_areas = self._identify_improvement_areas(
            speaking_times, word_counts, participation_patterns
        )
        strengths = self._identify_strengths(
            speaking_times, word_counts, participation_patterns
        )

        return {
            "speaking_style": speaking_style,
            "participation_patterns": participation_patterns_data,
            "performance_metrics": performance_metrics,
            "improvement_areas": improvement_areas,
            "strengths": strengths,
        }

    def validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate extracted performance data."""
        try:
            return validate_performance_data(data)
        except DataValidationError as e:
            self.logger.error(f"Performance data validation failed: {e.message}")
            raise

    def transform_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform performance data for database storage."""
        return {
            "speaking_style": data.get("speaking_style"),
            "participation_patterns": data.get("participation_patterns", {}),
            "performance_metrics": data.get("performance_metrics", {}),
            "improvement_areas": data.get("improvement_areas", {}),
            "strengths": data.get("strengths", {}),
        }

    def _create_empty_performance_data(self) -> Dict[str, Any]:
        """Create empty performance data structure."""
        return {
            "speaking_style": None,
            "participation_patterns": {},
            "performance_metrics": {},
            "improvement_areas": {},
            "strengths": {},
        }

    def _determine_speaking_style(
        self, speaking_times: List[float], word_counts: List[int]
    ) -> str:
        """Determine speaking style based on patterns."""
        if not speaking_times or not word_counts:
            return "balanced"

        # Calculate average speaking rate (words per second)
        total_time = sum(speaking_times)
        total_words = sum(word_counts)

        if total_time == 0:
            return "balanced"

        speaking_rate = total_words / total_time

        # Determine style based on speaking rate
        if speaking_rate > 3.0:
            return "fast"
        elif speaking_rate < 1.5:
            return "slow"
        else:
            return "balanced"

    def _analyze_participation_patterns(
        self, participation_patterns: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze participation patterns."""
        if not participation_patterns:
            return {}

        # Aggregate participation data
        total_participation = len(participation_patterns)
        participation_types = []

        for pattern in participation_patterns:
            participation_type = pattern.get("type", "unknown")
            participation_types.append(participation_type)

        type_counter = Counter(participation_types)

        return {
            "total_participations": total_participation,
            "participation_types": dict(type_counter),
            "most_common_type": (
                type_counter.most_common(1)[0][0] if type_counter else "unknown"
            ),
        }

    def _calculate_performance_metrics(
        self, speaking_times: List[float], word_counts: List[int]
    ) -> Dict[str, Any]:
        """Calculate performance metrics."""
        if not speaking_times or not word_counts:
            return {}

        total_time = sum(speaking_times)
        total_words = sum(word_counts)
        segment_count = len(speaking_times)

        # Calculate metrics
        avg_speaking_time = total_time / segment_count if segment_count > 0 else 0
        avg_word_count = total_words / segment_count if segment_count > 0 else 0
        speaking_rate = total_words / total_time if total_time > 0 else 0

        return {
            "total_speaking_time": total_time,
            "total_words": total_words,
            "segment_count": segment_count,
            "average_speaking_time": avg_speaking_time,
            "average_word_count": avg_word_count,
            "speaking_rate": speaking_rate,
        }

    def _identify_improvement_areas(
        self,
        speaking_times: List[float],
        word_counts: List[int],
        participation_patterns: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Identify areas for improvement."""
        improvement_areas = {}

        if speaking_times:
            # Check for speaking time consistency
            avg_time = sum(speaking_times) / len(speaking_times)
            time_variance = sum((t - avg_time) ** 2 for t in speaking_times) / len(
                speaking_times
            )

            if time_variance > avg_time * 0.5:
                improvement_areas["speaking_consistency"] = {
                    "issue": "Inconsistent speaking duration",
                    "suggestion": "Practice maintaining consistent speaking pace",
                }

        if word_counts:
            # Check for vocabulary diversity
            avg_words = sum(word_counts) / len(word_counts)
            if avg_words < 10:
                improvement_areas["vocabulary"] = {
                    "issue": "Limited vocabulary usage",
                    "suggestion": "Expand vocabulary and use more descriptive language",
                }

        return improvement_areas

    def _identify_strengths(
        self,
        speaking_times: List[float],
        word_counts: List[int],
        participation_patterns: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Identify speaker strengths."""
        strengths = {}

        if speaking_times:
            # Check for consistent speaking
            avg_time = sum(speaking_times) / len(speaking_times)
            time_variance = sum((t - avg_time) ** 2 for t in speaking_times) / len(
                speaking_times
            )

            if time_variance < avg_time * 0.2:
                strengths["speaking_consistency"] = {
                    "strength": "Consistent speaking pace",
                    "description": "Maintains steady speaking rhythm",
                }

        if word_counts:
            # Check for vocabulary richness
            avg_words = sum(word_counts) / len(word_counts)
            if avg_words > 20:
                strengths["vocabulary"] = {
                    "strength": "Rich vocabulary usage",
                    "description": "Uses diverse and descriptive language",
                }

        if participation_patterns:
            # Check for active participation
            if len(participation_patterns) > 5:
                strengths["participation"] = {
                    "strength": "Active participation",
                    "description": "Engages frequently in conversation",
                }

        return strengths
