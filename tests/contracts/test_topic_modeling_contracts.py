"""
Contract tests for the topic modeling analysis module (offline + deterministic).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from transcriptx.core.analysis.topic_modeling import TopicModelingAnalysis


class TestTopicModelingContracts:
    """Contract tests for TopicModelingAnalysis output shape."""

    @pytest.fixture
    def topic_module(self) -> TopicModelingAnalysis:
        """Fixture for TopicModelingAnalysis instance."""
        return TopicModelingAnalysis()

    @pytest.fixture
    def sample_segments(self) -> list[dict[str, Any]]:
        """Fixture for sample transcript segments with database-driven speaker identification."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I love machine learning and artificial intelligence.",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "Deep learning models are fascinating.",
                "start": 2.0,
                "end": 4.0,
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Neural networks can solve complex problems.",
                "start": 4.0,
                "end": 6.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "Python is great for data science.",
                "start": 6.0,
                "end": 8.0,
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Data analysis requires good tools.",
                "start": 8.0,
                "end": 10.0,
            },
        ]

    @pytest.fixture
    def sample_speaker_map(self) -> dict[str, str]:
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}

    def test_topic_modeling_empty_segments_output_contract(
        self, topic_module: TopicModelingAnalysis, sample_speaker_map: dict[str, str]
    ) -> None:
        """Assert analyze([]) returns error contract: error, message, topics, models, diagnostics."""
        result = topic_module.analyze([], sample_speaker_map)

        assert "error" in result
        assert "message" in result
        assert "topics" in result
        assert "models" in result
        assert isinstance(result["topics"], list)
        assert isinstance(result["models"], dict)
        assert "diagnostics" in result
        assert "total_segments" in result["diagnostics"]

    def test_topic_modeling_insufficient_segments_output_contract(
        self, topic_module: TopicModelingAnalysis, sample_speaker_map: dict[str, str]
    ) -> None:
        """Assert analyze() with 1–2 meaningful segments returns error contract with texts_count or diagnostics."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Only one segment.",
                "start": 0.0,
                "end": 1.0,
            },
        ]
        result = topic_module.analyze(segments, sample_speaker_map)

        assert "error" in result
        assert "topics" in result
        assert "models" in result
        assert "texts_count" in result or "diagnostics" in result

    @patch("transcriptx.core.analysis.topic_modeling.analysis.perform_enhanced_nmf_analysis")
    @patch("transcriptx.core.analysis.topic_modeling.analysis.perform_enhanced_lda_analysis")
    def test_topic_modeling_success_output_contract(
        self,
        mock_lda: MagicMock,
        mock_nmf: MagicMock,
        topic_module: TopicModelingAnalysis,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Assert successful analyze() returns required output keys."""
        # Minimal LDA/NMF result shapes (no model/vectorizer)
        doc_topic_data = [
            {
                "text": "a",
                "speaker": "Alice",
                "time": 0.0,
                "dominant_topic": 0,
                "topic_distribution": [1.0, 0.0],
                "confidence": 1.0,
            },
            {
                "text": "b",
                "speaker": "Bob",
                "time": 1.0,
                "dominant_topic": 0,
                "topic_distribution": [0.8, 0.2],
                "confidence": 0.8,
            },
            {
                "text": "c",
                "speaker": "Alice",
                "time": 2.0,
                "dominant_topic": 1,
                "topic_distribution": [0.2, 0.8],
                "confidence": 0.8,
            },
        ]
        lda_return = {
            "topics": [
                {
                    "topic_id": 0,
                    "words": ["word1"],
                    "weights": [1.0],
                    "label": "Topic 0",
                    "coherence": 0.1,
                }
            ],
            "doc_topics": np.array([[1.0, 0.0], [0.8, 0.2], [0.2, 0.8]]),
            "doc_topic_data": doc_topic_data,
            "diagnostics": {},
            "optimal_k": 2,
            "feature_names": ["word1", "word2"],
        }
        nmf_return = {
            "topics": [
                {
                    "topic_id": 0,
                    "words": ["word1"],
                    "weights": [1.0],
                    "label": "Topic 0",
                    "coherence": 0.1,
                }
            ],
            "doc_topics": np.array([[1.0, 0.0], [0.8, 0.2], [0.2, 0.8]]),
            "doc_topic_data": doc_topic_data,
            "diagnostics": {},
            "optimal_k": 2,
            "feature_names": ["word1", "word2"],
        }
        mock_lda.return_value = lda_return
        mock_nmf.return_value = nmf_return

        result = topic_module.analyze(sample_segments, sample_speaker_map)

        assert "error" not in result
        assert "lda_results" in result
        assert "nmf_results" in result
        assert "discourse_analysis" in result
        assert "texts" in result
        assert "speaker_labels" in result
        assert "time_labels" in result
        assert isinstance(result["lda_results"], dict)
        assert isinstance(result["nmf_results"], dict)
        assert "topics" in result["lda_results"]
        assert "doc_topic_data" in result["lda_results"]
        assert (
            "discourse_assignments" in result["discourse_analysis"]
            or "topic_prevalence" in result["discourse_analysis"]
        )
