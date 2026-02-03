"""Interaction data extractor for TranscriptX."""

import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from .base_extractor import BaseDataExtractor
from .validation import DataValidationError, validate_interaction_data

logger = logging.getLogger(__name__)


class InteractionDataExtractor(BaseDataExtractor):
    """Interaction data extractor for speaker-level interaction analysis."""

    def __init__(self):
        super().__init__("interactions")

    def extract_data(self, analysis_results: Dict[str, Any], speaker_id: str) -> Dict[str, Any]:
        try:
            speaker_id_int = int(speaker_id)
        except Exception:
            speaker_id_int = speaker_id  # type: ignore[assignment]
        return self.extract_speaker_data(analysis_results, speaker_id=speaker_id_int)  # type: ignore[arg-type]

    def extract_speaker_data(
        self, analysis_results: Dict[str, Any], speaker_id: int | str
    ) -> Dict[str, Any]:
        """Extract speaker-level interaction data from analysis results."""
        self.logger.info(f"Extracting interaction data for speaker {speaker_id}")

        speaker_segments = self.get_speaker_segments(analysis_results, speaker_id)

        if not speaker_segments:
            return self._create_empty_interaction_data()

        # Extract interaction data
        interruptions = []
        responses = []
        interactions = []

        for segment in speaker_segments:
            # Extract interaction patterns
            segment_interactions = segment.get("interactions", [])
            for interaction in segment_interactions:
                if isinstance(interaction, dict):
                    interaction_type = interaction.get("type", "")
                    target_speaker = interaction.get("target_speaker", "")
                    duration = interaction.get("duration", 0.0)

                    interactions.append(
                        {
                            "type": interaction_type,
                            "target": target_speaker,
                            "duration": duration,
                        }
                    )

                    if interaction_type == "interruption":
                        interruptions.append(interaction)
                    elif interaction_type == "response":
                        responses.append(interaction)

        # Calculate interaction metrics
        interaction_style = self._determine_interaction_style(interactions)
        interruption_patterns = self._analyze_interruption_patterns(interruptions)
        response_patterns = self._analyze_response_patterns(responses)
        interaction_network = self._calculate_interaction_network(interactions)
        influence_score = self._calculate_influence_score(interactions)
        collaboration_score = self._calculate_collaboration_score(interactions)

        return {
            "interaction_style": interaction_style,
            "interruption_patterns": interruption_patterns,
            "response_patterns": response_patterns,
            "interaction_network": interaction_network,
            "influence_score": influence_score,
            "collaboration_score": collaboration_score,
        }

    def validate_data(self, data: Dict[str, Any], speaker_id: str | None = None) -> bool:
        """Validate extracted interaction data."""
        try:
            return validate_interaction_data(data)
        except DataValidationError as e:
            self.logger.error(f"Interaction data validation failed: {e.message}")
            raise

    def transform_data(self, data: Dict[str, Any], speaker_id: str | None = None) -> Dict[str, Any]:
        """Transform interaction data for database storage."""
        return {
            "interaction_style": data.get("interaction_style"),
            "interruption_patterns": data.get("interruption_patterns", {}),
            "response_patterns": data.get("response_patterns", {}),
            "interaction_network": data.get("interaction_network", {}),
            "influence_score": data.get("influence_score"),
            "collaboration_score": data.get("collaboration_score"),
        }

    def _create_empty_interaction_data(self) -> Dict[str, Any]:
        """Create empty interaction data structure."""
        return {
            "interaction_style": None,
            "interruption_patterns": {},
            "response_patterns": {},
            "interaction_network": {},
            "influence_score": None,
            "collaboration_score": None,
        }

    def _determine_interaction_style(self, interactions: List[Dict[str, Any]]) -> str:
        """Determine interaction style based on patterns."""
        if not interactions:
            return "passive"

        # Count interaction types
        interaction_types = [i.get("type", "") for i in interactions]
        type_counter = Counter(interaction_types)

        # Determine style based on dominant patterns
        if type_counter.get("interruption", 0) > len(interactions) * 0.3:
            return "dominant"
        elif type_counter.get("response", 0) > len(interactions) * 0.5:
            return "responsive"
        elif len(interactions) > 10:
            return "active"
        else:
            return "passive"

    def _analyze_interruption_patterns(
        self, interruptions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze interruption patterns."""
        if not interruptions:
            return {}

        targets = [i.get("target", "") for i in interruptions]
        durations = [i.get("duration", 0.0) for i in interruptions]

        return {
            "interruption_count": len(interruptions),
            "target_distribution": dict(Counter(targets)),
            "average_duration": sum(durations) / len(durations) if durations else 0.0,
            "frequency": len(interruptions) / max(len(interruptions), 1),
        }

    def _analyze_response_patterns(
        self, responses: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze response patterns."""
        if not responses:
            return {}

        targets = [r.get("target", "") for r in responses]
        durations = [r.get("duration", 0.0) for r in responses]

        return {
            "response_count": len(responses),
            "target_distribution": dict(Counter(targets)),
            "average_duration": sum(durations) / len(durations) if durations else 0.0,
            "frequency": len(responses) / max(len(responses), 1),
        }

    def _calculate_interaction_network(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate interaction network."""
        if not interactions:
            return {}

        # Build network connections
        connections = {}
        for interaction in interactions:
            target = interaction.get("target", "")
            if target:
                if target not in connections:
                    connections[target] = {"count": 0, "duration": 0.0}
                connections[target]["count"] += 1
                connections[target]["duration"] += interaction.get("duration", 0.0)

        return {
            "connections": connections,
            "total_interactions": len(interactions),
            "unique_targets": len(connections),
        }

    def _calculate_influence_score(
        self, interactions: List[Dict[str, Any]]
    ) -> Optional[float]:
        """Calculate influence score."""
        if not interactions:
            return None

        # Influence based on interruptions and network centrality
        interruptions = [i for i in interactions if i.get("type") == "interruption"]
        influence_factors = []

        # Interruption factor
        if interruptions:
            interruption_ratio = len(interruptions) / len(interactions)
            influence_factors.append(interruption_ratio)

        # Network centrality factor
        targets = [i.get("target", "") for i in interactions if i.get("target")]
        if targets:
            unique_targets = len(set(targets))
            centrality = unique_targets / max(len(interactions), 1)
            influence_factors.append(centrality)

        return (
            sum(influence_factors) / len(influence_factors)
            if influence_factors
            else None
        )

    def _calculate_collaboration_score(
        self, interactions: List[Dict[str, Any]]
    ) -> Optional[float]:
        """Calculate collaboration score."""
        if not interactions:
            return None

        # Collaboration based on responses and positive interactions
        responses = [i for i in interactions if i.get("type") == "response"]
        collaboration_factors = []

        # Response factor
        if responses:
            response_ratio = len(responses) / len(interactions)
            collaboration_factors.append(response_ratio)

        # Interaction diversity factor
        targets = [i.get("target", "") for i in interactions if i.get("target")]
        if targets:
            diversity = len(set(targets)) / max(len(targets), 1)
            collaboration_factors.append(diversity)

        return (
            sum(collaboration_factors) / len(collaboration_factors)
            if collaboration_factors
            else None
        )
