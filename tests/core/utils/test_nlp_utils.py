"""
Tests for NLP helper functions.

This module tests stopwords, tics, preprocessing, and speaker normalization.
"""

from unittest.mock import patch, MagicMock

import pytest

from transcriptx.core.utils.nlp_utils import (
    load_custom_stopwords,
    load_tic_phrases,
    is_tic,
    extract_tics_from_text,
    preprocess_for_analysis,
)


class TestLoadCustomStopwords:
    """Tests for load_custom_stopwords function."""
    
    def test_loads_stopwords_from_file(self, tmp_path):
        """Test that stopwords are loaded from file."""
        stopwords_file = tmp_path / "stopwords.json"
        stopwords_file.write_text('["word1", "word2", "word3"]')
        
        with patch('transcriptx.core.utils.nlp_utils.STOPWORDS_FILE', stopwords_file):
            stopwords = load_custom_stopwords()
            
            assert isinstance(stopwords, set)
            assert "word1" in stopwords
            assert "word2" in stopwords
    
    def test_returns_empty_set_when_file_not_exists(self, tmp_path):
        """Test that empty set is returned when file doesn't exist."""
        stopwords_file = tmp_path / "nonexistent.json"
        
        with patch('transcriptx.core.utils.nlp_utils.STOPWORDS_FILE', stopwords_file):
            stopwords = load_custom_stopwords()
            
            assert isinstance(stopwords, set)
            assert len(stopwords) == 0


class TestLoadTicPhrases:
    """Tests for load_tic_phrases function."""
    
    def test_loads_tic_phrases_from_file(self, tmp_path):
        """Test that tic phrases are loaded from file."""
        tics_file = tmp_path / "tics.json"
        tics_data = {
            "category1": ["um", "uh"],
            "category2": ["like", "you know"]
        }
        tics_file.write_text(str(tics_data).replace("'", '"'))
        
        with patch('transcriptx.core.utils.nlp_utils.TICS_FILE', tics_file):
            tics = load_tic_phrases()
            
            assert isinstance(tics, dict)
            assert "category1" in tics or len(tics) > 0
    
    def test_returns_empty_dict_when_file_not_exists(self, tmp_path):
        """Test that empty dict is returned when file doesn't exist."""
        tics_file = tmp_path / "nonexistent.json"
        
        with patch('transcriptx.core.utils.nlp_utils.TICS_FILE', tics_file):
            tics = load_tic_phrases()
            
            assert isinstance(tics, dict)


class TestIsTic:
    """Tests for is_tic function."""
    
    def test_identifies_tic_phrases(self):
        """Test that tic phrases are identified."""
        with patch('transcriptx.core.utils.nlp_utils.ALL_VERBAL_TICS', {"um", "uh", "like"}):
            assert is_tic("um") is True
            assert is_tic("UM") is True  # Case insensitive
            assert is_tic("like") is True
    
    def test_rejects_non_tic_phrases(self):
        """Test that non-tic phrases are rejected."""
        with patch('transcriptx.core.utils.nlp_utils.ALL_VERBAL_TICS', {"um", "uh"}):
            assert is_tic("hello") is False
            assert is_tic("world") is False


class TestExtractTicsFromText:
    """Tests for extract_tics_from_text function."""
    
    def test_extracts_tics_from_text(self):
        """Test that tics are extracted from text."""
        with patch('transcriptx.core.utils.nlp_utils.ALL_VERBAL_TICS', {"um", "uh", "like"}):
            text = "Hello um world like this"
            tics = extract_tics_from_text(text)
            
            assert isinstance(tics, list)
            assert "um" in tics or "like" in tics
    
    def test_returns_empty_list_when_no_tics(self):
        """Test that empty list is returned when no tics found."""
        with patch('transcriptx.core.utils.nlp_utils.ALL_VERBAL_TICS', {"um", "uh"}):
            text = "Hello world this is a test"
            tics = extract_tics_from_text(text)
            
            assert isinstance(tics, list)
            assert len(tics) == 0


class TestPreprocessForAnalysis:
    """Tests for preprocess_for_analysis function."""
    
    def test_preprocesses_text(self):
        """Test that text is preprocessed."""
        text = "Hello, world! This is a test."
        
        result = preprocess_for_analysis(text)
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_handles_empty_text(self):
        """Test that empty text is handled."""
        result = preprocess_for_analysis("")
        
        assert isinstance(result, str)
    
    def test_removes_special_characters(self):
        """Test that special characters are handled."""
        text = "Hello!!! World??? Test---"
        
        result = preprocess_for_analysis(text)
        
        # Should process text (may remove or normalize special chars)
        assert isinstance(result, str)
