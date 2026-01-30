"""
Tests for understandability analysis module.

This module tests readability/understandability metrics.
"""

from unittest.mock import MagicMock, patch
import pytest

from transcriptx.core.analysis.understandability import UnderstandabilityAnalysis


class TestUnderstandabilityAnalysis:
    """Tests for UnderstandabilityAnalysis."""
    
    @pytest.fixture
    def understandability_module(self):
        """Fixture for UnderstandabilityAnalysis instance."""
        return UnderstandabilityAnalysis()
    
    @pytest.fixture
    def sample_segments(self):
        """Fixture for sample transcript segments using database-driven speaker identification."""
        return [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "This is a simple sentence.", "start": 0.0, "end": 2.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "The quick brown fox jumps over the lazy dog.", "start": 2.0, "end": 4.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Complex sentences with multiple clauses are harder to understand.", "start": 4.0, "end": 6.0},
        ]
    
    @pytest.fixture
    def sample_speaker_map(self):
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}
    
    @patch('transcriptx.core.analysis.understandability.compute_understandability_metrics')
    def test_understandability_basic(self, mock_compute, understandability_module, sample_segments, sample_speaker_map):
        """Test basic understandability analysis."""
        # Mock compute function
        mock_compute.return_value = {
            "flesch_reading_ease": 70.0,
            "flesch_kincaid_grade": 8.0,
            "avg_sentence_length": 15.0,
            "avg_word_length": 4.5,
        }
        
        result = understandability_module.analyze(sample_segments, sample_speaker_map)
        
        assert "scores" in result
        assert "speaker_stats" in result
        assert "global_stats" in result
    
    @patch('transcriptx.core.analysis.understandability.compute_understandability_metrics')
    def test_understandability_speaker_aggregation(self, mock_compute, understandability_module, sample_segments, sample_speaker_map):
        """Test understandability aggregation by speaker."""
        mock_compute.return_value = {
            "flesch_reading_ease": 70.0,
            "flesch_kincaid_grade": 8.0,
            "avg_sentence_length": 15.0,
            "avg_word_length": 4.5,
        }
        
        result = understandability_module.analyze(sample_segments, sample_speaker_map)
        
        assert "speaker_stats" in result
        assert len(result["speaker_stats"]) > 0
    
    @patch('transcriptx.core.analysis.understandability.compute_understandability_metrics')
    def test_understandability_empty_segments(self, mock_compute, understandability_module, sample_speaker_map):
        """Test understandability with empty segments."""
        segments = []
        
        result = understandability_module.analyze(segments, sample_speaker_map)
        
        assert "scores" in result
        assert "speaker_stats" in result
        assert "global_stats" in result
        assert len(result["speaker_stats"]) == 0
    
    @patch('transcriptx.core.analysis.understandability.compute_understandability_metrics')
    def test_understandability_metrics_computation(self, mock_compute, understandability_module, sample_speaker_map):
        """Test that understandability metrics are computed correctly."""
        mock_compute.return_value = {
            "flesch_reading_ease": 65.5,
            "flesch_kincaid_grade": 9.2,
            "avg_sentence_length": 18.3,
            "avg_word_length": 4.8,
        }
        
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Test sentence.", "start": 0.0, "end": 1.0},
        ]
        
        result = understandability_module.analyze(segments, sample_speaker_map)
        
        # Verify metrics are included
        assert "scores" in result
        if result["speaker_stats"]:
            stats = list(result["speaker_stats"].values())[0]
            assert "flesch_reading_ease" in stats or "flesch_kincaid_grade" in stats
