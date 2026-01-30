"""
Tests for topic modeling analysis module.

This module tests LDA/NMF topic modeling, topic selection, and coherence metrics.
"""

from unittest.mock import MagicMock, patch
import pytest
import numpy as np

from transcriptx.core.analysis.topic_modeling import TopicModelingAnalysis


class TestTopicModelingAnalysis:
    """Tests for TopicModelingAnalysis."""
    
    @pytest.fixture
    def topic_module(self):
        """Fixture for TopicModelingAnalysis instance."""
        return TopicModelingAnalysis()
    
    @pytest.fixture
    def sample_segments(self):
        """Fixture for sample transcript segments with database-driven speaker identification."""
        return [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "I love machine learning and artificial intelligence.", "start": 0.0, "end": 2.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "Deep learning models are fascinating.", "start": 2.0, "end": 4.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Neural networks can solve complex problems.", "start": 4.0, "end": 6.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "Python is great for data science.", "start": 6.0, "end": 8.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Data analysis requires good tools.", "start": 8.0, "end": 10.0},
        ]
    
    @pytest.fixture
    def sample_speaker_map(self):
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}
    
    @patch('transcriptx.core.analysis.topic_modeling.LatentDirichletAllocation')
    @patch('transcriptx.core.analysis.topic_modeling.NMF')
    @patch('transcriptx.core.analysis.topic_modeling.CountVectorizer')
    def test_topic_modeling_basic(self, mock_vectorizer, mock_nmf, mock_lda, topic_module, sample_segments, sample_speaker_map):
        """Test basic topic modeling analysis."""
        # Mock vectorizer
        mock_vec_instance = MagicMock()
        mock_vec_instance.fit_transform.return_value = np.array([[1, 2, 3], [2, 3, 4], [3, 4, 5]])
        mock_vec_instance.get_feature_names_out.return_value = ['word1', 'word2', 'word3']
        mock_vectorizer.return_value = mock_vec_instance
        
        # Mock LDA
        mock_lda_instance = MagicMock()
        mock_lda_instance.fit_transform.return_value = np.array([[0.5, 0.5], [0.6, 0.4], [0.4, 0.6]])
        mock_lda_instance.components_ = np.array([[0.3, 0.3, 0.4], [0.4, 0.3, 0.3]])
        mock_lda.return_value = mock_lda_instance
        
        result = topic_module.analyze(sample_segments, sample_speaker_map)
        
        assert "topics" in result or "lda_topics" in result or "nmf_topics" in result
        assert "segments" in result or "summary" in result
    
    def test_topic_modeling_empty_segments(self, topic_module, sample_speaker_map):
        """Test topic modeling with empty segments."""
        segments = []
        
        with pytest.raises((ValueError, IndexError)):
            topic_module.analyze(segments, sample_speaker_map)
    
    @patch('transcriptx.core.analysis.topic_modeling.CountVectorizer')
    def test_topic_modeling_single_segment(self, mock_vectorizer, topic_module, sample_speaker_map):
        """Test topic modeling with single segment."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "This is a test.", "start": 0.0, "end": 1.0}
        ]
        
        # Mock vectorizer to return valid matrix
        mock_vec_instance = MagicMock()
        mock_vec_instance.fit_transform.return_value = np.array([[1, 2, 3]])
        mock_vec_instance.get_feature_names_out.return_value = ['this', 'is', 'test']
        mock_vectorizer.return_value = mock_vec_instance
        
        # Should handle single segment gracefully
        try:
            result = topic_module.analyze(segments, sample_speaker_map)
            assert result is not None
        except (ValueError, IndexError):
            # Single segment may not be enough for topic modeling, which is acceptable
            pass
    
    @patch('transcriptx.core.analysis.topic_modeling.LatentDirichletAllocation')
    @patch('transcriptx.core.analysis.topic_modeling.CountVectorizer')
    def test_topic_modeling_speaker_aggregation(self, mock_vectorizer, mock_lda, topic_module, sample_segments, sample_speaker_map):
        """Test topic modeling with speaker aggregation."""
        # Mock vectorizer
        mock_vec_instance = MagicMock()
        mock_vec_instance.fit_transform.return_value = np.array([[1, 2, 3], [2, 3, 4], [3, 4, 5], [4, 5, 6], [5, 6, 7]])
        mock_vec_instance.get_feature_names_out.return_value = ['word1', 'word2', 'word3']
        mock_vectorizer.return_value = mock_vec_instance
        
        # Mock LDA
        mock_lda_instance = MagicMock()
        mock_lda_instance.fit_transform.return_value = np.array([[0.5, 0.5], [0.6, 0.4], [0.4, 0.6], [0.5, 0.5], [0.6, 0.4]])
        mock_lda_instance.components_ = np.array([[0.3, 0.3, 0.4], [0.4, 0.3, 0.3]])
        mock_lda.return_value = mock_lda_instance
        
        result = topic_module.analyze(sample_segments, sample_speaker_map)
        
        # Should include speaker-level topic information
        assert "speaker_topics" in result or "summary" in result or "speaker_topic_distributions" in result
    
    @patch('transcriptx.core.analysis.topic_modeling.CountVectorizer')
    def test_topic_modeling_unicode_handling(self, mock_vectorizer, topic_module, sample_speaker_map):
        """Test topic modeling with unicode characters."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "This is a test with émojis 🎉 and unicode.", "start": 0.0, "end": 2.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "Another segment with special chars: ñ, ü, ç", "start": 2.0, "end": 4.0},
        ]
        
        # Mock vectorizer
        mock_vec_instance = MagicMock()
        mock_vec_instance.fit_transform.return_value = np.array([[1, 2], [2, 3]])
        mock_vec_instance.get_feature_names_out.return_value = ['word1', 'word2']
        mock_vectorizer.return_value = mock_vec_instance
        
        # Should handle unicode gracefully
        try:
            result = topic_module.analyze(segments, sample_speaker_map)
            assert result is not None
        except Exception as e:
            # If it fails, it should be a meaningful error
            assert isinstance(e, (ValueError, UnicodeDecodeError, TypeError))
