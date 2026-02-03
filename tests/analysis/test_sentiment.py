"""
Tests for sentiment analysis module.

This module tests sentiment analysis output contracts (offline-safe).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.sentiment import SentimentAnalysis  # type: ignore[import-untyped]


class TestSentimentAnalysisModule:
    """Tests for SentimentAnalysis."""
    
    @pytest.fixture
    def sentiment_module(self) -> SentimentAnalysis:
        """Fixture for SentimentAnalysis instance."""
        return SentimentAnalysis()
    
    @pytest.fixture
    def sample_segments(self) -> list[dict[str, Any]]:
        """Fixture for sample transcript segments with database-driven speaker identification."""
        return [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "I love this product!", "start": 0.0, "end": 2.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "This is terrible.", "start": 2.0, "end": 4.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "It's okay, I guess.", "start": 4.0, "end": 6.0}
        ]
    
    @pytest.fixture
    def sample_speaker_map(self) -> dict[str, str]:
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}
    
    def test_sentiment_analysis_basic(
        self,
        sentiment_module: SentimentAnalysis,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test basic sentiment analysis."""
        result = sentiment_module.analyze(sample_segments, sample_speaker_map)
        
        assert "segments_with_sentiment" in result
        segments = result["segments_with_sentiment"]
        assert len(segments) == len(sample_segments)
        for seg in segments:
            sentiment = seg.get("sentiment")
            assert isinstance(sentiment, dict)
            assert {"compound", "pos", "neu", "neg"}.issubset(set(sentiment.keys()))
            # normalized keys are a stable contract across backends
            assert "sentiment_compound_norm" in seg
            assert -1.0 <= float(seg["sentiment_compound_norm"]) <= 1.0
    
    def test_sentiment_analysis_positive_text(
        self, sentiment_module: SentimentAnalysis, sample_speaker_map: dict[str, str]
    ) -> None:
        """Test sentiment analysis on positive text."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "This is amazing! I love it!", "start": 0.0, "end": 2.0}
        ]
        
        result = sentiment_module.analyze(segments, sample_speaker_map)
        
        # Should detect positive sentiment
        sentiment = result["segments_with_sentiment"][0]["sentiment"]
        assert float(sentiment.get("compound", 0.0)) > 0
    
    def test_sentiment_analysis_negative_text(
        self, sentiment_module: SentimentAnalysis, sample_speaker_map: dict[str, str]
    ) -> None:
        """Test sentiment analysis on negative text."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "This is terrible. I hate it.", "start": 0.0, "end": 2.0}
        ]
        
        result = sentiment_module.analyze(segments, sample_speaker_map)
        
        # Should detect negative sentiment
        sentiment = result["segments_with_sentiment"][0]["sentiment"]
        assert float(sentiment.get("compound", 0.0)) < 0
    
    def test_sentiment_analysis_neutral_text(
        self, sentiment_module: SentimentAnalysis, sample_speaker_map: dict[str, str]
    ) -> None:
        """Test sentiment analysis on neutral text."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "The weather is fine today.", "start": 0.0, "end": 2.0}
        ]
        
        result = sentiment_module.analyze(segments, sample_speaker_map)
        
        # Should detect neutral sentiment
        sentiment = result["segments_with_sentiment"][0]["sentiment"]
        assert abs(float(sentiment.get("compound", 0.0))) < 0.4
    
    def test_sentiment_analysis_speaker_aggregation(
        self,
        sentiment_module: SentimentAnalysis,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test sentiment aggregation by speaker."""
        result = sentiment_module.analyze(sample_segments, sample_speaker_map)
        
        # Should include speaker-level aggregation
        assert "speaker_analysis" in result
        assert "speaker_stats" in result
    
    def test_sentiment_analysis_empty_segments(
        self, sentiment_module: SentimentAnalysis, sample_speaker_map: dict[str, str]
    ) -> None:
        """Test sentiment analysis with empty segments."""
        segments: list[dict[str, Any]] = []
        
        result = sentiment_module.analyze(segments, sample_speaker_map)
        
        assert "segments_with_sentiment" in result
        assert result["segments_with_sentiment"] == []

    def test_sentiment_smoke_charts(
        self,
        sentiment_module: SentimentAnalysis,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
        temp_transcript_file: Any,
    ) -> None:
        """Smoke test for chart + data writes (contract only)."""
        results = sentiment_module.analyze(sample_segments, sample_speaker_map)

        output_service = MagicMock()
        output_service.base_name = "test_transcript"
        output_service.transcript_path = str(temp_transcript_file)
        output_service.save_data = MagicMock()
        output_service.save_chart = MagicMock()
        output_service.save_summary = MagicMock()

        with patch(
            "transcriptx.core.analysis.sentiment.get_enriched_transcript_path",
            return_value=str(temp_transcript_file),
        ), patch(
            "transcriptx.core.analysis.sentiment.save_transcript"
        ):
            sentiment_module._save_results(results, output_service)

        assert output_service.save_data.called
        assert output_service.save_chart.called or output_service.save_summary.called
