"""
Entity data extractor for TranscriptX.

This module provides the EntityDataExtractor class that extracts speaker-level
NER data from analysis results and transforms it for database storage.
"""

import logging
from collections import Counter
from typing import Any, Dict, List

from .base_extractor import BaseDataExtractor
from .validation import DataValidationError, validate_entity_data

logger = logging.getLogger(__name__)


class EntityDataExtractor(BaseDataExtractor):
    """
    Entity data extractor for speaker-level NER analysis.

    This extractor processes NER analysis results and extracts speaker-specific
    entity data including expertise domains, frequently mentioned entities, and networks.
    """

    def __init__(self):
        """Initialize the entity data extractor."""
        super().__init__("ner")

    def extract_data(self, analysis_results: Dict[str, Any], speaker_id: str) -> Dict[str, Any]:
        """
        BaseDataExtractor interface: extract speaker-level data.

        `speaker_id` is a string in the base protocol; we accept numeric strings too.
        """
        try:
            speaker_id_int = int(speaker_id)
        except Exception:
            speaker_id_int = speaker_id  # type: ignore[assignment]
        return self.extract_speaker_data(analysis_results, speaker_id=speaker_id_int)  # type: ignore[arg-type]

    def extract_speaker_data(
        self, analysis_results: Dict[str, Any], speaker_id: int | str
    ) -> Dict[str, Any]:
        """
        Extract speaker-level entity data from analysis results.

        Args:
            analysis_results: Complete analysis results for the conversation
            speaker_id: ID of the speaker to extract data for

        Returns:
            Dictionary containing extracted entity data

        Raises:
            ValueError: If required data is missing or invalid
            DataValidationError: If extracted data fails validation
        """
        self.logger.info(f"Extracting entity data for speaker {speaker_id}")

        # Get speaker segments
        speaker_segments = self.get_speaker_segments(analysis_results, speaker_id)

        if not speaker_segments:
            self.logger.warning(f"No segments found for speaker {speaker_id}")
            return self._create_empty_entity_data()

        # Extract entity data
        all_entities = []
        entity_types = []
        entity_sentiments = {}

        for segment in speaker_segments:
            # Extract entities from segment
            entities = segment.get("entities", [])
            for entity in entities:
                if isinstance(entity, dict):
                    entity_text = entity.get("text", "")
                    entity_type = entity.get("type", "")
                    entity_sentiment = entity.get("sentiment", 0.0)

                    if entity_text and entity_type:
                        all_entities.append(entity_text)
                        entity_types.append(entity_type)

                        if entity_text not in entity_sentiments:
                            entity_sentiments[entity_text] = []
                        entity_sentiments[entity_text].append(entity_sentiment)

        # Calculate entity metrics
        entity_expertise_domains = self._calculate_expertise_domains(entity_types)
        frequently_mentioned_entities = self._calculate_frequently_mentioned_entities(
            all_entities
        )
        entity_network = self._calculate_entity_network(all_entities, entity_types)
        entity_sentiment_patterns = self._calculate_entity_sentiment_patterns(
            entity_sentiments
        )
        entity_evolution = self._calculate_entity_evolution(speaker_segments)

        # Create entity data
        entity_data = {
            "entity_expertise_domains": entity_expertise_domains,
            "frequently_mentioned_entities": frequently_mentioned_entities,
            "entity_network": entity_network,
            "entity_sentiment_patterns": entity_sentiment_patterns,
            "entity_evolution": entity_evolution,
        }

        self.logger.info(
            f"Extracted entity data for speaker {speaker_id}: "
            f"domains={len(entity_expertise_domains)}, "
            f"entities={len(frequently_mentioned_entities)}"
        )

        return entity_data

    def validate_data(self, data: Dict[str, Any], speaker_id: str | None = None) -> bool:
        """
        Validate extracted entity data.

        Args:
            data: Extracted entity data to validate

        Returns:
            True if data is valid

        Raises:
            DataValidationError: If data fails validation
        """
        try:
            return validate_entity_data(data)
        except DataValidationError as e:
            self.logger.error(f"Entity data validation failed: {e.message}")
            raise

    def transform_data(self, data: Dict[str, Any], speaker_id: str | None = None) -> Dict[str, Any]:
        """
        Transform entity data for database storage.

        Args:
            data: Raw extracted entity data

        Returns:
            Transformed data ready for database storage
        """
        # Ensure all required fields are present
        transformed_data = {
            "entity_expertise_domains": data.get("entity_expertise_domains", {}),
            "frequently_mentioned_entities": data.get(
                "frequently_mentioned_entities", {}
            ),
            "entity_network": data.get("entity_network", {}),
            "entity_sentiment_patterns": data.get("entity_sentiment_patterns", {}),
            "entity_evolution": data.get("entity_evolution", {}),
        }

        return transformed_data

    def _create_empty_entity_data(self) -> Dict[str, Any]:
        """
        Create empty entity data structure.

        Returns:
            Empty entity data structure
        """
        return {
            "entity_expertise_domains": {},
            "frequently_mentioned_entities": {},
            "entity_network": {},
            "entity_sentiment_patterns": {},
            "entity_evolution": {},
        }

    def _calculate_expertise_domains(self, entity_types: List[str]) -> Dict[str, float]:
        """
        Calculate expertise domains based on entity types.

        Args:
            entity_types: List of entity types

        Returns:
            Dictionary mapping domains to expertise scores
        """
        if not entity_types:
            return {}

        # Count entity types
        type_counter = Counter(entity_types)
        total_entities = len(entity_types)

        # Calculate expertise scores
        expertise_domains = {}
        for entity_type, count in type_counter.items():
            expertise_score = count / total_entities
            expertise_domains[entity_type] = expertise_score

        return expertise_domains

    def _calculate_frequently_mentioned_entities(
        self, entities: List[str]
    ) -> Dict[str, int]:
        """
        Calculate frequently mentioned entities.

        Args:
            entities: List of entity texts

        Returns:
            Dictionary mapping entities to mention counts
        """
        if not entities:
            return {}

        # Count entity mentions
        entity_counter = Counter(entities)

        # Return top entities
        return dict(entity_counter.most_common(20))

    def _calculate_entity_network(
        self, entities: List[str], entity_types: List[str]
    ) -> Dict[str, Any]:
        """
        Calculate entity network relationships.

        Args:
            entities: List of entity texts
            entity_types: List of entity types

        Returns:
            Dictionary containing entity network data
        """
        if not entities or not entity_types:
            return {}

        # Create entity-type mapping
        entity_type_map = {}
        for i, entity in enumerate(entities):
            if i < len(entity_types):
                entity_type_map[entity] = entity_types[i]

        # Calculate network metrics
        network_data = {
            "entity_count": len(set(entities)),
            "type_count": len(set(entity_types)),
            "entity_type_mapping": entity_type_map,
            "type_distribution": dict(Counter(entity_types)),
        }

        return network_data

    def _calculate_entity_sentiment_patterns(
        self, entity_sentiments: Dict[str, List[float]]
    ) -> Dict[str, Any]:
        """
        Calculate sentiment patterns for entities.

        Args:
            entity_sentiments: Dictionary mapping entities to sentiment scores

        Returns:
            Dictionary containing entity sentiment patterns
        """
        if not entity_sentiments:
            return {}

        sentiment_patterns = {}

        for entity, sentiments in entity_sentiments.items():
            if sentiments:
                avg_sentiment = sum(sentiments) / len(sentiments)
                sentiment_patterns[entity] = {
                    "average_sentiment": avg_sentiment,
                    "sentiment_count": len(sentiments),
                    "sentiment_volatility": self.calculate_volatility(sentiments),
                }

        return sentiment_patterns

    def _calculate_entity_evolution(
        self, speaker_segments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate entity evolution over time.

        Args:
            speaker_segments: List of speaker segments

        Returns:
            Dictionary containing entity evolution data
        """
        if len(speaker_segments) < 2:
            return {}

        # Track entities over time
        entity_timeline = []

        for segment in speaker_segments:
            entities = segment.get("entities", [])
            segment_entities = []

            for entity in entities:
                if isinstance(entity, dict):
                    entity_text = entity.get("text", "")
                    if entity_text:
                        segment_entities.append(entity_text)

            entity_timeline.append(segment_entities)

        # Calculate evolution metrics
        unique_entities = set()
        for entities in entity_timeline:
            unique_entities.update(entities)

        evolution_data = {
            "total_unique_entities": len(unique_entities),
            "entity_timeline": entity_timeline,
            "evolution_rate": len(unique_entities) / max(len(speaker_segments), 1),
        }

        return evolution_data
