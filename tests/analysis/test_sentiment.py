"""
Tests for sentiment analysis module.

This module tests sentiment analysis logic and VADER integration.
"""

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.sentiment import SentimentAnalysis


class TestSentimentAnalysisModule:
    """Tests for SentimentAnalysis."""
    
    @pytest.fixture
    def sentiment_module(self):
        """Fixture for SentimentAnalysis instance."""
        return SentimentAnalysis()
    
    @pytest.fixture
    def sample_segments(self):
        """Fixture for sample transcript segments with database-driven speaker identification."""
        return [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "I love this product!", "start": 0.0, "end": 2.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "This is terrible.", "start": 2.0, "end": 4.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "It's okay, I guess.", "start": 4.0, "end": 6.0}
        ]
    
    @pytest.fixture
    def sample_speaker_map(self):
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}
    
    def test_sentiment_analysis_basic(self, sentiment_module, sample_segments, sample_speaker_map):
        """Test basic sentiment analysis."""
        result = sentiment_module.analyze(sample_segments, sample_speaker_map)
        
        assert "segments" in result
        assert len(result["segments"]) == len(sample_segments)
        assert all("sentiment" in seg for seg in result["segments"])
    
    def test_sentiment_analysis_positive_text(self, sentiment_module, sample_speaker_map):
        """Test sentiment analysis on positive text."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "This is amazing! I love it!", "start": 0.0, "end": 2.0}
        ]
        
        result = sentiment_module.analyze(segments, sample_speaker_map)
        
        # Should detect positive sentiment
        sentiment = result["segments"][0]["sentiment"]
        assert sentiment in ["positive", "compound"] or sentiment.get("compound", 0) > 0
    
    def test_sentiment_analysis_negative_text(self, sentiment_module, sample_speaker_map):
        """Test sentiment analysis on negative text."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "This is terrible. I hate it.", "start": 0.0, "end": 2.0}
        ]
        
        result = sentiment_module.analyze(segments, sample_speaker_map)
        
        # Should detect negative sentiment
        sentiment = result["segments"][0]["sentiment"]
        assert sentiment in ["negative", "compound"] or sentiment.get("compound", 0) < 0
    
    def test_sentiment_analysis_neutral_text(self, sentiment_module, sample_speaker_map):
        """Test sentiment analysis on neutral text."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "The weather is fine today.", "start": 0.0, "end": 2.0}
        ]
        
        result = sentiment_module.analyze(segments, sample_speaker_map)
        
        # Should detect neutral sentiment
        sentiment = result["segments"][0]["sentiment"]
        assert sentiment in ["neutral", "compound"] or abs(sentiment.get("compound", 0)) < 0.1
    
    def test_sentiment_analysis_speaker_aggregation(self, sentiment_module, sample_segments, sample_speaker_map):
        """Test sentiment aggregation by speaker."""
        result = sentiment_module.analyze(sample_segments, sample_speaker_map)
        
        # Should include speaker-level aggregation
        assert "speaker_sentiment" in result or "summary" in result
    
    def test_sentiment_analysis_empty_segments(self, sentiment_module, sample_speaker_map):
        """Test sentiment analysis with empty segments."""
        segments = []
        
        result = sentiment_module.analyze(segments, sample_speaker_map)
        
        assert "segments" in result
        assert len(result["segments"]) == 0

    def test_sentiment_smoke_charts(
        self, sentiment_module, sample_segments, sample_speaker_map, temp_transcript_file
    ):
        """Smoke test for static + dynamic chart generation."""
        results = sentiment_module.analyze(sample_segments, sample_speaker_map)

        output_service = MagicMock()
        output_service.base_name = "test_transcript"
        output_service.transcript_path = str(temp_transcript_file)
        output_service.should_generate_dynamic.return_value = True

        with patch(
            "transcriptx.core.analysis.sentiment.get_enriched_transcript_path",
            return_value=str(temp_transcript_file),
        ), patch(
            "transcriptx.core.analysis.sentiment.save_transcript"
        ), patch.object(
            sentiment_module, "_create_rolling_sentiment_plot", return_value=MagicMock()
        ), patch.object(
            sentiment_module,
            "_create_rolling_sentiment_plot_plotly",
            return_value=MagicMock(),
        ), patch.object(
            sentiment_module, "_create_multi_speaker_plot", return_value=MagicMock()
        ), patch.object(
            sentiment_module,
            "_create_multi_speaker_plot_plotly",
            return_value=MagicMock(),
        ):
            sentiment_module._save_results(results, output_service)

        assert output_service.save_chart.called
        rolling_calls = [
            call
            for call in output_service.save_chart.call_args_list
            if call.kwargs.get("chart_id") == "rolling_sentiment"
            and call.kwargs.get("scope") == "speaker"
            and call.kwargs.get("dynamic_fig") is not None
        ]
        multi_calls = [
            call
            for call in output_service.save_chart.call_args_list
            if call.kwargs.get("chart_id") == "multi_speaker_sentiment"
            and call.kwargs.get("scope") == "global"
            and call.kwargs.get("dynamic_fig") is not None
        ]
        assert rolling_calls
        assert multi_calls
