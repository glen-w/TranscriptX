"""
Tests for advanced semantic similarity analysis module.

This module tests advanced similarity with embeddings.
"""

from unittest.mock import MagicMock, patch
import pytest
import numpy as np

from transcriptx.core.analysis.semantic_similarity import SemanticSimilarityAdvancedAnalysis


class TestSemanticSimilarityAdvancedAnalysis:
    """Tests for SemanticSimilarityAdvancedAnalysis."""
    
    @pytest.fixture
    def advanced_similarity_module(self):
        """Fixture for SemanticSimilarityAdvancedAnalysis instance."""
        return SemanticSimilarityAdvancedAnalysis()
    
    @pytest.fixture
    def sample_segments(self):
        """Fixture for sample transcript segments using database-driven speaker identification."""
        return [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "I love machine learning and AI.", "start": 0.0, "end": 2.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "I also love artificial intelligence.", "start": 2.0, "end": 4.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Deep learning models are powerful.", "start": 4.0, "end": 6.0},
        ]
    
    @pytest.fixture
    def sample_speaker_map(self):
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}
    
    @patch('transcriptx.core.analysis.semantic_similarity.analysis.AdvancedSemanticSimilarityAnalyzer')
    def test_advanced_similarity_basic(self, mock_analyzer_class, advanced_similarity_module, sample_segments, sample_speaker_map):
        """Test basic advanced semantic similarity analysis."""
        # Mock analyzer
        mock_analyzer = MagicMock()
        mock_analyzer.detect_repetitions.return_value = {
            "repetitions": [],
            "quality_scores": {},
            "summary": {}
        }
        mock_analyzer_class.return_value = mock_analyzer
        
        result = advanced_similarity_module.analyze(sample_segments, sample_speaker_map)
        
        assert "repetitions" in result or "quality_scores" in result or "summary" in result
    
    @patch('transcriptx.core.analysis.semantic_similarity.analysis.AdvancedSemanticSimilarityAnalyzer')
    def test_advanced_similarity_with_embeddings(self, mock_analyzer_class, advanced_similarity_module, sample_segments, sample_speaker_map):
        """Test advanced similarity with transformer embeddings."""
        # Mock analyzer
        mock_analyzer = MagicMock()
        mock_analyzer.detect_repetitions.return_value = {
            "repetitions": [],
            "embeddings": np.random.rand(3, 768),
            "summary": {}
        }
        mock_analyzer_class.return_value = mock_analyzer
        
        result = advanced_similarity_module.analyze(sample_segments, sample_speaker_map)
        
        assert result is not None
    
    @patch('transcriptx.core.analysis.semantic_similarity_advanced.AdvancedSemanticSimilarityAnalyzer')
    def test_advanced_similarity_quality_scoring(self, mock_analyzer_class, advanced_similarity_module, sample_segments, sample_speaker_map):
        """Test quality scoring in advanced similarity."""
        mock_analyzer = MagicMock()
        mock_analyzer.detect_repetitions.return_value = {
            "repetitions": [],
            "quality_scores": {
                "segment_0": 0.8,
                "segment_1": 0.9,
            },
            "summary": {}
        }
        mock_analyzer_class.return_value = mock_analyzer
        
        result = advanced_similarity_module.analyze(sample_segments, sample_speaker_map)
        
        assert "quality_scores" in result or "summary" in result
    
    def test_advanced_similarity_empty_segments(self, advanced_similarity_module, sample_speaker_map):
        """Test advanced similarity with empty segments."""
        segments = []
        
        with patch('transcriptx.core.analysis.semantic_similarity_advanced.AdvancedSemanticSimilarityAnalyzer') as mock_analyzer_class:
            mock_analyzer = MagicMock()
            mock_analyzer.detect_repetitions.return_value = {"repetitions": [], "summary": {}}
            mock_analyzer_class.return_value = mock_analyzer
            
            result = advanced_similarity_module.analyze(segments, sample_speaker_map)
            
            assert result is not None
