"""
Tests for entity sentiment analysis module.

This module tests entity-focused sentiment analysis.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch
import pytest

from transcriptx.core.analysis.entity_sentiment import EntitySentimentAnalysis


class TestEntitySentimentAnalysis:
    """Tests for EntitySentimentAnalysis."""

    @pytest.fixture
    def entity_sentiment_module(self) -> EntitySentimentAnalysis:
        """Fixture for EntitySentimentAnalysis instance."""
        return EntitySentimentAnalysis()

    @pytest.fixture
    def sample_segments(self) -> list[dict[str, Any]]:
        """Fixture for sample transcript segments using database-driven speaker identification."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I love Python programming.",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "Python is great for data science.",
                "start": 2.0,
                "end": 4.0,
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I hate Java though.",
                "start": 4.0,
                "end": 6.0,
            },
        ]

    @pytest.fixture
    def sample_speaker_map(self) -> dict[str, str]:
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}

    @patch("transcriptx.core.analysis.entity_sentiment.extract_named_entities")
    @patch("transcriptx.core.analysis.entity_sentiment.score_sentiment")
    def test_entity_sentiment_basic(
        self,
        mock_sentiment: Any,
        mock_ner: Any,
        entity_sentiment_module: EntitySentimentAnalysis,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test basic entity sentiment analysis."""
        # Mock NER to return entities
        # Core implementation expects list[tuple[text, label]]
        mock_ner.return_value = [("Python", "ORG"), ("Java", "ORG"), ("Python", "ORG")]

        # Mock sentiment scoring
        # score_sentiment() returns a VADER-like dict contract
        mock_sentiment.return_value = {
            "compound": 0.5,
            "pos": 0.6,
            "neu": 0.3,
            "neg": 0.1,
        }

        result = entity_sentiment_module.analyze(sample_segments, sample_speaker_map)

        assert "entity_sentiment" in result
        assert "entities" in result
        assert "summary" in result
        # Python should be included because it is mentioned >= 2 times
        assert "Python" in result["entities"]

    @patch("transcriptx.core.analysis.entity_sentiment.extract_named_entities")
    def test_entity_sentiment_with_ner_data(
        self,
        mock_ner: Any,
        entity_sentiment_module: EntitySentimentAnalysis,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test entity sentiment analysis with pre-computed NER data."""
        ner_data = {
            "entities": [
                {"text": "Python", "label": "ORG", "start": 10, "end": 16},
            ],
            "segments": sample_segments,
        }

        # When compute is used, extract_named_entities returns tuples; cached ner_data is not parsed yet.
        mock_ner.return_value = [("Python", "ORG"), ("Python", "ORG")]

        result = entity_sentiment_module.analyze(
            sample_segments, sample_speaker_map, ner_data=ner_data
        )

        assert result is not None
        assert "entity_sentiment" in result

    @patch("transcriptx.core.analysis.entity_sentiment.extract_named_entities")
    @patch("transcriptx.core.analysis.entity_sentiment.score_sentiment")
    def test_entity_sentiment_speaker_aggregation(
        self,
        mock_sentiment: Any,
        mock_ner: Any,
        entity_sentiment_module: EntitySentimentAnalysis,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test entity sentiment aggregation by speaker."""
        mock_ner.return_value = [("Python", "ORG"), ("Python", "ORG")]
        mock_sentiment.return_value = {
            "compound": 0.5,
            "pos": 0.6,
            "neu": 0.3,
            "neg": 0.1,
        }

        result = entity_sentiment_module.analyze(sample_segments, sample_speaker_map)

        # Should include speaker-level entity sentiment
        assert "speaker_entity_sentiment" in result

    @patch("transcriptx.core.analysis.entity_sentiment.extract_named_entities")
    def test_entity_sentiment_no_entities(
        self,
        mock_ner: Any,
        entity_sentiment_module: EntitySentimentAnalysis,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test entity sentiment analysis with no entities found."""
        mock_ner.return_value = []

        result = entity_sentiment_module.analyze(sample_segments, sample_speaker_map)

        # Should handle gracefully
        assert result is not None
        assert (
            "entity_sentiment" in result or "entities" in result or "summary" in result
        )

    def test_entity_sentiment_empty_segments(
        self,
        entity_sentiment_module: EntitySentimentAnalysis,
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test entity sentiment analysis with empty segments."""
        segments = []

        result = entity_sentiment_module.analyze(segments, sample_speaker_map)

        # Should handle empty segments
        assert result is not None
        assert (
            "entity_sentiment" in result or "entities" in result or "summary" in result
        )

    def test_entity_name_normalization(
        self, entity_sentiment_module: EntitySentimentAnalysis
    ) -> None:
        """Test entity name normalization."""
        from transcriptx.core.analysis.entity_sentiment import normalize_entity_name

        # Test normalization
        assert normalize_entity_name("u.s.") == "United States"
        assert normalize_entity_name("USA") == "United States"
        assert normalize_entity_name("Python") == "Python"  # No normalization needed
