"""
Tests for statistical analysis module.

This module tests statistical analysis and metrics calculation.
"""

from unittest.mock import MagicMock

import pytest

from transcriptx.core.analysis.stats import StatsAnalysis


class TestStatisticalAnalysisModule:
    """Tests for StatsAnalysis."""
    
    @pytest.fixture
    def stats_module(self):
        """Fixture for StatsAnalysis instance."""
        return StatsAnalysis()
    
    @pytest.fixture
    def sample_segments(self):
        """Fixture for sample transcript segments with database-driven speaker identification."""
        return [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Hello world", "start": 0.0, "end": 1.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "How are you?", "start": 1.0, "end": 2.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "I'm fine, thanks!", "start": 2.0, "end": 3.0}
        ]
    
    @pytest.fixture
    def sample_speaker_map(self):
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}
    
    def test_stats_analysis_basic(self, stats_module, sample_segments, sample_speaker_map):
        """Test basic statistical analysis."""
        result = stats_module.analyze(sample_segments, sample_speaker_map)
        
        assert "summary" in result or "statistics" in result
        assert "total_segments" in result or "segments" in result
    
    def test_stats_analysis_word_count(self, stats_module, sample_segments, sample_speaker_map):
        """Test word count calculation."""
        result = stats_module.analyze(sample_segments, sample_speaker_map)
        
        # Should include word count statistics
        assert "word_count" in result or "total_words" in result or "words" in result
    
    def test_stats_analysis_speaker_stats(self, stats_module, sample_segments, sample_speaker_map):
        """Test speaker-level statistics."""
        result = stats_module.analyze(sample_segments, sample_speaker_map)
        
        # Should include speaker statistics
        assert "speaker_stats" in result or "speakers" in result
    
    def test_stats_analysis_duration_stats(self, stats_module, sample_segments, sample_speaker_map):
        """Test duration statistics."""
        result = stats_module.analyze(sample_segments, sample_speaker_map)
        
        # Should include duration statistics
        assert "duration" in result or "total_duration" in result or "time" in result
    
    def test_stats_analysis_empty_segments(self, stats_module, sample_speaker_map):
        """Test statistical analysis with empty segments."""
        segments = []
        
        result = stats_module.analyze(segments, sample_speaker_map)
        
        # Should handle empty segments gracefully
        assert "summary" in result or "statistics" in result
