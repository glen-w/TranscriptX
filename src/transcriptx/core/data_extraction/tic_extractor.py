"""Tic data extractor for TranscriptX."""

import logging
from collections import Counter
from typing import Any, Dict, List

from .base_extractor import BaseDataExtractor
from .validation import DataValidationError, validate_tic_data

logger = logging.getLogger(__name__)


class TicDataExtractor(BaseDataExtractor):
    """Tic data extractor for speaker-level verbal tics analysis."""

    def __init__(self):
        super().__init__("tics")

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
        """Extract speaker-level tic data from analysis results."""
        self.logger.info(f"Extracting tic data for speaker {speaker_id}")

        speaker_segments = self.get_speaker_segments(analysis_results, speaker_id)

        if not speaker_segments:
            return self._create_empty_tic_data()

        # Extract tic data
        all_tics = []
        tic_types = []
        tic_contexts = []

        for segment in speaker_segments:
            tics = segment.get("tics", [])
            for tic in tics:
                if isinstance(tic, dict):
                    tic_text = tic.get("text", "")
                    tic_type = tic.get("type", "")
                    context = tic.get("context", "")

                    if tic_text:
                        all_tics.append(tic_text)
                        tic_types.append(tic_type)
                        tic_contexts.append(context)

        # Calculate tic metrics
        tic_frequency = self._calculate_tic_frequency(all_tics)
        tic_types_dist = self._calculate_tic_types(tic_types)
        tic_context_patterns = self._calculate_context_patterns(tic_contexts)
        tic_evolution = self._calculate_tic_evolution(speaker_segments)
        tic_reduction_goals = self._generate_reduction_goals(
            tic_frequency, tic_types_dist
        )
        tic_confidence_indicators = self._calculate_confidence_indicators(all_tics)

        return {
            "tic_frequency": tic_frequency,
            "tic_types": tic_types_dist,
            "tic_context_patterns": tic_context_patterns,
            "tic_evolution": tic_evolution,
            "tic_reduction_goals": tic_reduction_goals,
            "tic_confidence_indicators": tic_confidence_indicators,
        }

    def validate_data(
        self, data: Dict[str, Any], speaker_id: str | None = None
    ) -> bool:
        """Validate extracted tic data."""
        try:
            return validate_tic_data(data)
        except DataValidationError as e:
            self.logger.error(f"Tic data validation failed: {e.message}")
            raise

    def transform_data(
        self, data: Dict[str, Any], speaker_id: str | None = None
    ) -> Dict[str, Any]:
        """Transform tic data for database storage."""
        return {
            "tic_frequency": data.get("tic_frequency", {}),
            "tic_types": data.get("tic_types", {}),
            "tic_context_patterns": data.get("tic_context_patterns", {}),
            "tic_evolution": data.get("tic_evolution", {}),
            "tic_reduction_goals": data.get("tic_reduction_goals", {}),
            "tic_confidence_indicators": data.get("tic_confidence_indicators", {}),
        }

    def _create_empty_tic_data(self) -> Dict[str, Any]:
        """Create empty tic data structure."""
        return {
            "tic_frequency": {},
            "tic_types": {},
            "tic_context_patterns": {},
            "tic_evolution": {},
            "tic_reduction_goals": {},
            "tic_confidence_indicators": {},
        }

    def _calculate_tic_frequency(self, tics: List[str]) -> Dict[str, int]:
        """Calculate tic frequency."""
        if not tics:
            return {}
        return dict(Counter(tics))

    def _calculate_tic_types(self, tic_types: List[str]) -> Dict[str, float]:
        """Calculate tic type distribution."""
        if not tic_types:
            return {}
        counter = Counter(tic_types)
        total = len(tic_types)
        return {tic_type: count / total for tic_type, count in counter.items()}

    def _calculate_context_patterns(self, contexts: List[str]) -> Dict[str, Any]:
        """Calculate context patterns."""
        if not contexts:
            return {}
        counter = Counter(contexts)
        return {
            "context_distribution": dict(counter),
            "total_contexts": len(contexts),
            "unique_contexts": len(set(contexts)),
        }

    def _calculate_tic_evolution(
        self, speaker_segments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate tic evolution over time."""
        if len(speaker_segments) < 2:
            return {}

        tic_timeline = []
        for segment in speaker_segments:
            tics = segment.get("tics", [])
            tic_count = len(tics)
            tic_timeline.append(tic_count)

        return {
            "tic_timeline": tic_timeline,
            "total_tics": sum(tic_timeline),
            "average_tics_per_segment": (
                sum(tic_timeline) / len(tic_timeline) if tic_timeline else 0
            ),
        }

    def _generate_reduction_goals(
        self, tic_frequency: Dict[str, int], tic_types: Dict[str, float]
    ) -> Dict[str, Any]:
        """Generate tic reduction goals."""
        if not tic_frequency:
            return {}

        # Identify most frequent tics for reduction
        sorted_tics = sorted(tic_frequency.items(), key=lambda x: x[1], reverse=True)
        top_tics = sorted_tics[:5]

        goals = {}
        for tic, frequency in top_tics:
            goals[tic] = {
                "current_frequency": frequency,
                "target_frequency": max(0, frequency - 1),
                "reduction_percentage": 20.0,
            }

        return goals

    def _calculate_confidence_indicators(self, tics: List[str]) -> Dict[str, float]:
        """Calculate confidence indicators for tic detection."""
        if not tics:
            return {}

        # Simple confidence based on frequency
        counter = Counter(tics)
        total_tics = len(tics)

        confidence_indicators = {}
        for tic, count in counter.items():
            confidence = min(1.0, count / max(total_tics, 1))
            confidence_indicators[tic] = confidence

        return confidence_indicators
