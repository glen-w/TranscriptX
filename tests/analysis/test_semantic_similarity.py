"""
Tests for semantic similarity analysis module.

This module tests basic similarity detection.
"""

from unittest.mock import MagicMock, patch
import pytest
import numpy as np

from transcriptx.core.analysis.semantic_similarity import SemanticSimilarityAnalysis


class TestSemanticSimilarityAnalysis:
    """Tests for SemanticSimilarityAnalysis."""
    
    @pytest.fixture
    def similarity_module(self):
        """Fixture for SemanticSimilarityAnalysis instance."""
        return SemanticSimilarityAnalysis()
    
    @pytest.fixture
    def sample_segments(self):
        """Fixture for sample transcript segments."""
        return [
            {"speaker": "SPEAKER_00", "text": "I love machine learning.", "start": 0.0, "end": 2.0},
            {"speaker": "SPEAKER_01", "text": "I also love machine learning.", "start": 2.0, "end": 4.0},
            {"speaker": "SPEAKER_00", "text": "Deep learning is fascinating.", "start": 4.0, "end": 6.0},
        ]
    
    @pytest.fixture
    def sample_speaker_map(self):
        """Fixture for sample speaker map."""
        return {
            "SPEAKER_00": "Alice",
            "SPEAKER_01": "Bob"
        }
    
    @patch('transcriptx.core.analysis.semantic_similarity.analysis.SemanticSimilarityAnalyzer')
    def test_semantic_similarity_basic(self, mock_analyzer_class, similarity_module, sample_segments, sample_speaker_map):
        """Test basic semantic similarity analysis."""
        # Mock analyzer
        mock_analyzer = MagicMock()
        mock_analyzer.detect_repetitions.return_value = {
            "repetitions": [],
            "similarity_matrix": np.array([[1.0, 0.8], [0.8, 1.0]]),
            "summary": {}
        }
        mock_analyzer_class.return_value = mock_analyzer
        
        result = similarity_module.analyze(sample_segments, sample_speaker_map)
        
        assert "repetitions" in result or "similarity" in result or "summary" in result
    
    @patch('transcriptx.core.analysis.semantic_similarity.analysis.SemanticSimilarityAnalyzer')
    def test_semantic_similarity_repetition_detection(self, mock_analyzer_class, similarity_module, sample_segments, sample_speaker_map):
        """Test repetition detection."""
        mock_analyzer = MagicMock()
        mock_analyzer.detect_repetitions.return_value = {
            "repetitions": [
                {"segment1": 0, "segment2": 1, "similarity": 0.95}
            ],
            "summary": {"total_repetitions": 1}
        }
        mock_analyzer_class.return_value = mock_analyzer
        
        result = similarity_module.analyze(sample_segments, sample_speaker_map)
        
        assert "repetitions" in result or "similarity" in result
    
    def test_semantic_similarity_empty_segments(self, similarity_module, sample_speaker_map):
        """Test semantic similarity with empty segments."""
        segments = []
        
        with patch('transcriptx.core.analysis.semantic_similarity.analysis.SemanticSimilarityAnalyzer') as mock_analyzer_class:
            mock_analyzer = MagicMock()
            mock_analyzer.detect_repetitions.return_value = {"repetitions": [], "summary": {}}
            mock_analyzer_class.return_value = mock_analyzer
            
            result = similarity_module.analyze(segments, sample_speaker_map)
            
            assert result is not None
    
    @patch('transcriptx.core.analysis.semantic_similarity.analysis.SemanticSimilarityAnalyzer')
    def test_semantic_similarity_speaker_aggregation(self, mock_analyzer_class, similarity_module, sample_segments, sample_speaker_map):
        """Test semantic similarity with speaker aggregation."""
        mock_analyzer = MagicMock()
        mock_analyzer.detect_repetitions.return_value = {
            "repetitions": [],
            "speaker_similarity": {"Alice": {}, "Bob": {}},
            "summary": {}
        }
        mock_analyzer_class.return_value = mock_analyzer
        
        result = similarity_module.analyze(sample_segments, sample_speaker_map)
        
        assert "speaker_similarity" in result or "summary" in result
