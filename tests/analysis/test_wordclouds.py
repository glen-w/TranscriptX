"""
Tests for wordclouds analysis module.

This module tests word cloud generation.
"""

from unittest.mock import MagicMock, patch
import pytest

from transcriptx.core.analysis.wordclouds import WordcloudsAnalysis


class TestWordcloudsAnalysis:
    """Tests for WordcloudsAnalysis."""
    
    @pytest.fixture
    def wordclouds_module(self):
        """Fixture for WordcloudsAnalysis instance."""
        return WordcloudsAnalysis()
    
    @pytest.fixture
    def sample_segments(self):
        """Fixture for sample transcript segments with database-driven speaker identification."""
        return [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "I love machine learning and data science.", "start": 0.0, "end": 2.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "Python is great for programming and analysis.", "start": 2.0, "end": 4.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Deep learning models are fascinating.", "start": 4.0, "end": 6.0},
        ]
    
    @pytest.fixture
    def sample_speaker_map(self):
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}
    
    @patch('transcriptx.core.analysis.wordclouds.group_texts_by_speaker')
    @patch('transcriptx.core.analysis.wordclouds.extract_tics_and_top_words')
    def test_wordclouds_basic(self, mock_extract_tics, mock_group_texts, wordclouds_module, sample_segments, sample_speaker_map):
        """Test basic wordcloud analysis."""
        # Mock group_texts
        mock_group_texts.return_value = {
            "Alice": ["I love machine learning and data science.", "Deep learning models are fascinating."],
            "Bob": ["Python is great for programming and analysis."],
        }
        
        # Mock extract_tics
        mock_extract_tics.return_value = ({}, {})
        
        result = wordclouds_module.analyze(sample_segments, sample_speaker_map)
        
        assert "grouped_texts" in result
    
    @patch('transcriptx.core.analysis.wordclouds.group_texts_by_speaker')
    def test_wordclouds_with_tic_list(self, mock_group_texts, wordclouds_module, sample_segments, sample_speaker_map):
        """Test wordcloud analysis with provided tic list."""
        mock_group_texts.return_value = {
            "Alice": ["I love machine learning."],
            "Bob": ["Python is great."],
        }
        
        tic_list = ["um", "uh", "like"]
        
        result = wordclouds_module.analyze(sample_segments, sample_speaker_map, tic_list=tic_list)
        
        assert "tic_list" in result
        assert result["tic_list"] == tic_list
    
    @patch('transcriptx.core.analysis.wordclouds.group_texts_by_speaker')
    def test_wordclouds_empty_segments(self, mock_group_texts, wordclouds_module, sample_speaker_map):
        """Test wordcloud analysis with empty segments."""
        segments = []
        mock_group_texts.return_value = {}
        
        result = wordclouds_module.analyze(segments, sample_speaker_map)
        
        assert "grouped_texts" in result
    
    @patch('transcriptx.core.analysis.wordclouds.WordCloud')
    @patch('transcriptx.core.analysis.wordclouds.group_texts_by_speaker')
    def test_wordcloud_generation(self, mock_group_texts, mock_wordcloud, wordclouds_module, sample_segments, sample_speaker_map):
        """Test wordcloud generation."""
        mock_group_texts.return_value = {
            "Alice": ["I love machine learning."],
        }
        
        # Mock WordCloud
        mock_wc_instance = MagicMock()
        mock_wc_instance.generate_from_text.return_value = MagicMock()
        mock_wordcloud.return_value = mock_wc_instance
        
        result = wordclouds_module.analyze(sample_segments, sample_speaker_map)
        
        # Should return grouped texts for wordcloud generation
        assert "grouped_texts" in result
