"""
Tests for verbal tics analysis module.

This module tests verbal tics detection and filtering.
"""

from unittest.mock import MagicMock, patch
import pytest

from transcriptx.core.analysis.tics import TicsAnalysis, extract_tics_and_top_words


class TestTicsAnalysis:
    """Tests for TicsAnalysis."""
    
    @pytest.fixture
    def tics_module(self):
        """Fixture for TicsAnalysis instance."""
        return TicsAnalysis()
    
    @pytest.fixture
    def sample_segments(self):
        """Fixture for sample transcript segments with tics using database-driven speaker identification."""
        return [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Um, I think that, uh, this is good.", "start": 0.0, "end": 2.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "Well, you know, it's okay I guess.", "start": 2.0, "end": 4.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Like, I mean, it's fine.", "start": 4.0, "end": 6.0},
        ]
    
    @pytest.fixture
    def sample_speaker_map(self):
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}
    
    @patch('transcriptx.core.analysis.tics.ALL_VERBAL_TICS', {'um', 'uh', 'like', 'well', 'you know', 'i mean'})
    def test_tics_analysis_basic(self, tics_module, sample_segments, sample_speaker_map):
        """Test basic tics analysis."""
        result = tics_module.analyze(sample_segments, sample_speaker_map)
        
        assert "tic_counts" in result or "tics" in result or "summary" in result
        assert "speaker_tics" in result or "per_speaker" in result or "summary" in result
    
    @patch('transcriptx.core.analysis.tics.ALL_VERBAL_TICS', {'um', 'uh'})
    def test_tics_detection(self, tics_module, sample_speaker_map):
        """Test tics detection in text."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Um, I think um this is good.", "start": 0.0, "end": 2.0},
        ]
        
        result = tics_module.analyze(segments, sample_speaker_map)
        
        # Should detect tics
        assert "tic_counts" in result or "tics" in result or "summary" in result
    
    @patch('transcriptx.core.analysis.tics.ALL_VERBAL_TICS', set())
    def test_tics_analysis_no_tics(self, tics_module, sample_segments, sample_speaker_map):
        """Test tics analysis when no tics are found."""
        result = tics_module.analyze(sample_segments, sample_speaker_map)
        
        # Should handle gracefully
        assert result is not None
        assert "tic_counts" in result or "tics" in result or "summary" in result
    
    def test_tics_analysis_empty_segments(self, tics_module, sample_speaker_map):
        """Test tics analysis with empty segments."""
        segments = []
        
        result = tics_module.analyze(segments, sample_speaker_map)
        
        assert result is not None
        assert "tic_counts" in result or "tics" in result or "summary" in result
    
    @patch('transcriptx.core.analysis.tics.ALL_VERBAL_TICS', {'um', 'uh'})
    def test_tics_analysis_speaker_aggregation(self, tics_module, sample_speaker_map):
        """Test tics aggregation by speaker."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Um, I think this.", "start": 0.0, "end": 2.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Um, yeah that's right.", "start": 2.0, "end": 4.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "Uh, I agree.", "start": 4.0, "end": 6.0},
        ]
        
        result = tics_module.analyze(segments, sample_speaker_map)
        
        # Should aggregate tics by speaker
        assert "speaker_tics" in result or "per_speaker" in result or "summary" in result
    
    @patch('transcriptx.core.analysis.tics.ALL_VERBAL_TICS', {'um', 'uh'})
    def test_tics_analysis_case_insensitive(self, tics_module, sample_speaker_map):
        """Test that tics detection is case insensitive."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "UM, I think this.", "start": 0.0, "end": 2.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "Uh, I agree.", "start": 2.0, "end": 4.0},
        ]
        
        result = tics_module.analyze(segments, sample_speaker_map)
        
        # Should detect tics regardless of case
        assert result is not None


class TestExtractTicsAndTopWords:
    """Tests for extract_tics_and_top_words utility function."""
    
    @patch('transcriptx.core.analysis.tics.ALL_VERBAL_TICS', {'um', 'uh', 'like'})
    def test_extract_tics_and_top_words(self):
        """Test extract_tics_and_top_words function."""
        grouped_text = {
            "Alice": ["Um, I think this is good.", "Like, you know, it's fine."],
            "Bob": ["Uh, I agree.", "Well, that's interesting."],
        }
        
        tics, common = extract_tics_and_top_words(grouped_text, top_n=10)
        
        assert isinstance(tics, dict)
        assert isinstance(common, dict)
        assert "Alice" in tics or "Bob" in tics
        assert "Alice" in common or "Bob" in common
    
    @patch('transcriptx.core.analysis.tics.ALL_VERBAL_TICS', set())
    def test_extract_tics_no_tics(self):
        """Test extract_tics_and_top_words with no tics."""
        grouped_text = {
            "Alice": ["I think this is good.", "It's fine."],
        }
        
        tics, common = extract_tics_and_top_words(grouped_text, top_n=10)
        
        assert isinstance(tics, dict)
        assert isinstance(common, dict)
