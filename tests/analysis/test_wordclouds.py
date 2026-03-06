"""
Tests for wordclouds analysis module.

This module tests word cloud generation.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch
import pytest

from transcriptx.core.analysis.wordclouds import WordcloudsAnalysis  # type: ignore[import-untyped]


class TestWordcloudsAnalysis:
    """Tests for WordcloudsAnalysis."""

    @pytest.fixture
    def wordclouds_module(self) -> WordcloudsAnalysis:
        """Fixture for WordcloudsAnalysis instance."""
        return WordcloudsAnalysis()

    @pytest.fixture
    def sample_segments(self) -> list[dict[str, Any]]:
        """Fixture for sample transcript segments with database-driven speaker identification."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I love machine learning and data science.",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "Python is great for programming and analysis.",
                "start": 2.0,
                "end": 4.0,
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Deep learning models are fascinating.",
                "start": 4.0,
                "end": 6.0,
            },
        ]

    @pytest.fixture
    def sample_speaker_map(self) -> dict[str, str]:
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}

    @patch("transcriptx.core.analysis.wordclouds.analysis.group_texts_by_speaker")
    def test_wordclouds_basic(
        self,
        mock_group_texts: Any,
        wordclouds_module: WordcloudsAnalysis,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test basic wordcloud analysis."""
        # Mock group_texts
        mock_group_texts.return_value = {
            "Alice": [
                "I love machine learning and data science.",
                "Deep learning models are fascinating.",
            ],
            "Bob": ["Python is great for programming and analysis."],
        }

        # Provide tic_list explicitly to keep this test pure/offline.
        result = wordclouds_module.analyze(
            sample_segments, sample_speaker_map, tic_list=[]
        )

        assert "grouped_texts" in result

    @patch("transcriptx.core.analysis.wordclouds.analysis.group_texts_by_speaker")
    def test_wordclouds_with_tic_list(
        self,
        mock_group_texts: Any,
        wordclouds_module: WordcloudsAnalysis,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test wordcloud analysis with provided tic list."""
        mock_group_texts.return_value = {
            "Alice": ["I love machine learning."],
            "Bob": ["Python is great."],
        }

        tic_list = ["um", "uh", "like"]

        result = wordclouds_module.analyze(
            sample_segments, sample_speaker_map, tic_list=tic_list
        )

        assert "tic_list" in result
        assert result["tic_list"] == tic_list

    @patch("transcriptx.core.analysis.wordclouds.analysis.group_texts_by_speaker")
    def test_wordclouds_empty_segments(
        self,
        mock_group_texts: Any,
        wordclouds_module: WordcloudsAnalysis,
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test wordcloud analysis with empty segments."""
        segments: list[dict[str, Any]] = []
        mock_group_texts.return_value = {}

        result = wordclouds_module.analyze(segments, sample_speaker_map, tic_list=[])

        assert "grouped_texts" in result
