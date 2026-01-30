"""
Tests for similarity calculation utilities.

This module tests text similarity, name similarity, and behavioral similarity.
"""

from unittest.mock import patch

import pytest

from transcriptx.core.utils.similarity_utils import (
    SimilarityCalculator,
    calculate_text_similarity,
    calculate_name_similarity,
    calculate_dict_similarity,
    calculate_behavioral_similarity,
    extract_vocabulary_patterns,
    similarity_calculator,
)


class TestSimilarityCalculator:
    """Tests for SimilarityCalculator class."""
    
    def test_initialization(self):
        """Test SimilarityCalculator initialization."""
        calculator = SimilarityCalculator()
        
        assert calculator is not None
        # TF-IDF may or may not be initialized
        assert hasattr(calculator, 'tfidf_vectorizer')
    
    def test_calculates_text_similarity_tfidf(self):
        """Test TF-IDF similarity calculation."""
        calculator = SimilarityCalculator()
        
        similarity = calculator.calculate_text_similarity(
            "Hello world",
            "Hello world",
            method="tfidf"
        )
        
        assert 0.0 <= similarity <= 1.0
        assert similarity > 0.5  # Same text should be very similar
    
    def test_calculates_text_similarity_jaccard(self):
        """Test Jaccard similarity calculation."""
        calculator = SimilarityCalculator()
        
        similarity = calculator.calculate_text_similarity(
            "Hello world",
            "Hello world",
            method="jaccard"
        )
        
        assert 0.0 <= similarity <= 1.0
    
    def test_returns_zero_for_empty_texts(self):
        """Test that zero is returned for empty texts."""
        calculator = SimilarityCalculator()
        
        similarity = calculator.calculate_text_similarity("", "Hello")
        
        assert similarity == 0.0
    
    def test_returns_one_for_identical_texts(self):
        """Test that one is returned for identical texts."""
        calculator = SimilarityCalculator()
        
        similarity = calculator.calculate_text_similarity("Hello", "Hello")
        
        assert similarity == 1.0
    
    def test_handles_unknown_method(self):
        """Test that unknown method falls back to TF-IDF."""
        calculator = SimilarityCalculator()
        
        similarity = calculator.calculate_text_similarity(
            "Hello",
            "World",
            method="unknown_method"
        )
        
        # Should not raise error, should return a value
        assert 0.0 <= similarity <= 1.0


class TestCalculateTextSimilarity:
    """Tests for calculate_text_similarity function."""
    
    def test_calculates_similarity(self):
        """Test that similarity is calculated."""
        similarity = calculate_text_similarity("Hello world", "Hello world")
        
        assert 0.0 <= similarity <= 1.0
    
    def test_handles_different_texts(self):
        """Test that different texts have lower similarity."""
        similarity = calculate_text_similarity("Hello world", "Goodbye universe")
        
        assert 0.0 <= similarity <= 1.0
        assert similarity < 1.0


class TestCalculateNameSimilarity:
    """Tests for calculate_name_similarity function."""
    
    def test_calculates_name_similarity(self):
        """Test that name similarity is calculated."""
        similarity = calculate_name_similarity("Alice", "Alice")
        
        assert 0.0 <= similarity <= 1.0
        assert similarity > 0.5  # Same name should be very similar
    
    def test_handles_similar_names(self):
        """Test that similar names have high similarity."""
        similarity = calculate_name_similarity("Alice", "Alicia")
        
        assert 0.0 <= similarity <= 1.0
    
    def test_handles_different_names(self):
        """Test that different names have lower similarity."""
        similarity = calculate_name_similarity("Alice", "Bob")
        
        assert 0.0 <= similarity <= 1.0
        assert similarity < 0.5  # Different names should be less similar
    
    def test_handles_case_differences(self):
        """Test that case differences are handled."""
        similarity = calculate_name_similarity("Alice", "alice")
        
        assert 0.0 <= similarity <= 1.0
        # Should be similar despite case difference
        assert similarity > 0.5


class TestSimilarityCalculatorAdvanced:
    """Advanced tests for SimilarityCalculator covering all methods."""
    
    @pytest.fixture
    def calculator(self):
        """Fixture for SimilarityCalculator instance."""
        return SimilarityCalculator()
    
    def test_all_similarity_methods(self, calculator):
        """Test all text similarity methods."""
        text1 = "Hello world this is a test"
        text2 = "Hello world this is another test"
        
        # TF-IDF
        tfidf_sim = calculator.calculate_text_similarity(text1, text2, method="tfidf")
        assert 0.0 <= tfidf_sim <= 1.0
        
        # Jaccard
        jaccard_sim = calculator.calculate_text_similarity(text1, text2, method="jaccard")
        assert 0.0 <= jaccard_sim <= 1.0
        
        # Cosine
        cosine_sim = calculator.calculate_text_similarity(text1, text2, method="cosine")
        assert 0.0 <= cosine_sim <= 1.0
        
        # Overlap
        overlap_sim = calculator.calculate_text_similarity(text1, text2, method="overlap")
        assert 0.0 <= overlap_sim <= 1.0
    
    def test_dictionary_similarity_methods(self, calculator):
        """Test all dictionary similarity methods."""
        dict1 = {"a": 1, "b": 2, "c": 3}
        dict2 = {"a": 1, "b": 3, "d": 4}
        
        # Weighted
        weighted_sim = calculator.calculate_dict_similarity(dict1, dict2, method="weighted")
        assert 0.0 <= weighted_sim <= 1.0
        
        # Jaccard (on keys)
        jaccard_sim = calculator.calculate_dict_similarity(dict1, dict2, method="jaccard")
        assert 0.0 <= jaccard_sim <= 1.0
        
        # Cosine (on values)
        cosine_sim = calculator.calculate_dict_similarity(dict1, dict2, method="cosine")
        assert 0.0 <= cosine_sim <= 1.0
    
    def test_behavioral_similarity(self, calculator):
        """Test behavioral similarity calculation."""
        fingerprint1 = {
            "vocabulary_patterns": {"python": 10, "coding": 5},
            "speech_patterns": {"average_speaking_rate": 150, "average_segment_duration": 3.5},
            "emotion_patterns": {"joy": 0.7, "sadness": 0.1},
            "sentiment_patterns": {"average_sentiment": 0.6}
        }
        
        fingerprint2 = {
            "vocabulary_patterns": {"python": 8, "coding": 6},
            "speech_patterns": {"average_speaking_rate": 145, "average_segment_duration": 3.2},
            "emotion_patterns": {"joy": 0.65, "sadness": 0.15},
            "sentiment_patterns": {"average_sentiment": 0.55}
        }
        
        similarity = calculator.calculate_behavioral_similarity(fingerprint1, fingerprint2)
        assert 0.0 <= similarity <= 1.0
    
    def test_behavioral_similarity_partial_data(self, calculator):
        """Test behavioral similarity with partial data."""
        fingerprint1 = {
            "vocabulary_patterns": {"python": 10}
            # Missing other patterns
        }
        
        fingerprint2 = {
            "vocabulary_patterns": {"python": 8},
            "speech_patterns": {"average_speaking_rate": 150}
        }
        
        similarity = calculator.calculate_behavioral_similarity(fingerprint1, fingerprint2)
        assert 0.0 <= similarity <= 1.0
    
    def test_vocabulary_pattern_extraction(self, calculator):
        """Test vocabulary pattern extraction."""
        texts = [
            "Python is a great programming language",
            "I love Python programming",
            "Python makes coding fun"
        ]
        
        patterns = calculator.extract_vocabulary_patterns(texts)
        
        assert "common_words" in patterns
        assert "word_frequencies" in patterns
        assert "total_words" in patterns
        assert "unique_words" in patterns
        assert isinstance(patterns["common_words"], list)
        assert isinstance(patterns["word_frequencies"], dict)
        assert patterns["total_words"] > 0
        assert "python" in [w.lower() for w in patterns["common_words"]]
    
    def test_vocabulary_pattern_extraction_empty(self, calculator):
        """Test vocabulary pattern extraction with empty input."""
        patterns = calculator.extract_vocabulary_patterns([])
        
        assert patterns["common_words"] == []
        assert patterns["word_frequencies"] == {}
        assert patterns["total_words"] == 0
        assert patterns["unique_words"] == 0
    
    def test_global_instance_usage(self):
        """Test that global instance works correctly."""
        # Test global instance exists
        assert similarity_calculator is not None
        assert isinstance(similarity_calculator, SimilarityCalculator)
        
        # Test it can calculate similarity
        similarity = similarity_calculator.calculate_text_similarity("hello", "world")
        assert 0.0 <= similarity <= 1.0
    
    def test_performance_large_texts(self, calculator):
        """Test similarity calculation with large texts."""
        # Create large texts
        text1 = " ".join(["word"] * 1000)
        text2 = " ".join(["word"] * 1000)
        
        # Should complete without error
        similarity = calculator.calculate_text_similarity(text1, text2)
        assert 0.0 <= similarity <= 1.0
    
    def test_unicode_handling(self, calculator):
        """Test Unicode and special character handling."""
        # Unicode text
        text1 = "Hello 世界"
        text2 = "Hello 世界"
        
        similarity = calculator.calculate_text_similarity(text1, text2)
        assert 0.0 <= similarity <= 1.0
        
        # Special characters
        text3 = "Hello! How are you? I'm fine."
        text4 = "Hello! How are you? I'm fine."
        
        similarity = calculator.calculate_text_similarity(text3, text4)
        assert 0.0 <= similarity <= 1.0
    
    def test_edge_cases_comprehensive(self, calculator):
        """Test comprehensive edge cases."""
        # Identical texts
        similarity = calculator.calculate_text_similarity("test", "test")
        assert similarity == 1.0
        
        # Completely different texts
        similarity = calculator.calculate_text_similarity("hello", "xyzabc")
        assert 0.0 <= similarity < 1.0
        
        # One empty text
        similarity = calculator.calculate_text_similarity("", "test")
        assert similarity == 0.0
        
        # Both empty
        similarity = calculator.calculate_text_similarity("", "")
        assert similarity == 0.0
        
        # Whitespace only
        similarity = calculator.calculate_text_similarity("   ", "test")
        assert similarity == 0.0
    
    def test_dict_similarity_edge_cases(self, calculator):
        """Test dictionary similarity edge cases."""
        # Empty dicts
        similarity = calculator.calculate_dict_similarity({}, {})
        assert similarity == 0.0
        
        # One empty dict
        similarity = calculator.calculate_dict_similarity({"a": 1}, {})
        assert similarity == 0.0
        
        # Identical dicts
        dict1 = {"a": 1, "b": 2}
        similarity = calculator.calculate_dict_similarity(dict1, dict1)
        assert similarity > 0.5  # Should be high similarity
    
    def test_name_similarity_edge_cases(self, calculator):
        """Test name similarity edge cases."""
        # Empty names
        similarity = calculator.calculate_name_similarity("", "")
        assert similarity == 0.0
        
        # One empty name
        similarity = calculator.calculate_name_similarity("Alice", "")
        assert similarity == 0.0
        
        # Names with prefixes
        similarity = calculator.calculate_name_similarity("Dr. Alice Smith", "Alice Smith")
        assert similarity > 0.5  # Should be similar despite prefix
    
    def test_tokenize_text(self, calculator):
        """Test text tokenization."""
        tokens = calculator._tokenize_text("Hello world! This is a test.")
        
        assert isinstance(tokens, list)
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens
        # Should filter out very short words
        assert all(len(token) > 2 for token in tokens)
    
    def test_normalize_name(self, calculator):
        """Test name normalization."""
        normalized = calculator._normalize_name("  Dr.  Alice  Smith  ")
        
        assert normalized == "alice smith"
        assert "dr" not in normalized
    
    def test_speech_similarity(self, calculator):
        """Test speech pattern similarity."""
        speech1 = {"average_speaking_rate": 150, "average_segment_duration": 3.5}
        speech2 = {"average_speaking_rate": 145, "average_segment_duration": 3.2}
        
        similarity = calculator._calculate_speech_similarity(speech1, speech2)
        assert 0.0 <= similarity <= 1.0
    
    def test_sentiment_similarity(self, calculator):
        """Test sentiment pattern similarity."""
        sentiment1 = {"average_sentiment": 0.6}
        sentiment2 = {"average_sentiment": 0.55}
        
        similarity = calculator._calculate_sentiment_similarity(sentiment1, sentiment2)
        assert 0.0 <= similarity <= 1.0


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_calculate_dict_similarity_function(self):
        """Test calculate_dict_similarity convenience function."""
        dict1 = {"a": 1, "b": 2}
        dict2 = {"a": 1, "b": 3}
        
        similarity = calculate_dict_similarity(dict1, dict2)
        assert 0.0 <= similarity <= 1.0
    
    def test_calculate_behavioral_similarity_function(self):
        """Test calculate_behavioral_similarity convenience function."""
        fingerprint1 = {
            "vocabulary_patterns": {"python": 10},
            "speech_patterns": {"average_speaking_rate": 150}
        }
        fingerprint2 = {
            "vocabulary_patterns": {"python": 8},
            "speech_patterns": {"average_speaking_rate": 145}
        }
        
        similarity = calculate_behavioral_similarity(fingerprint1, fingerprint2)
        assert 0.0 <= similarity <= 1.0
    
    def test_extract_vocabulary_patterns_function(self):
        """Test extract_vocabulary_patterns convenience function."""
        texts = ["Python is great", "I love Python"]
        
        patterns = extract_vocabulary_patterns(texts)
        
        assert "common_words" in patterns
        assert "word_frequencies" in patterns
        assert patterns["total_words"] > 0
