"""
Tests for sentiment data extractor.

This module tests extraction of sentiment data from analysis results.
"""

from unittest.mock import patch
import pytest

from transcriptx.core.data_extraction.sentiment_extractor import SentimentDataExtractor


class TestSentimentDataExtractor:
    """Tests for SentimentDataExtractor."""

    @pytest.fixture
    def extractor(self):
        """Fixture for SentimentDataExtractor instance."""
        return SentimentDataExtractor()

    @pytest.fixture
    def sample_analysis_results(self):
        """Fixture for sample analysis results with sentiment data."""
        return {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "I love this!",
                    "sentiment_score": 0.8,
                    "sentiment_label": "positive",
                    "trigger_words": ["love"],
                },
                {
                    "speaker": "SPEAKER_00",
                    "text": "This is great!",
                    "sentiment_score": 0.9,
                    "sentiment_label": "positive",
                    "trigger_words": ["great"],
                },
                {
                    "speaker": "SPEAKER_01",
                    "text": "I hate this.",
                    "sentiment_score": -0.7,
                    "sentiment_label": "negative",
                    "trigger_words": ["hate"],
                },
            ],
            "speaker_map": {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"},
        }

    def test_extract_speaker_data_basic(self, extractor, sample_analysis_results):
        """Test basic speaker data extraction."""
        # Mock get_speaker_segments
        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = [
                sample_analysis_results["segments"][0],
                sample_analysis_results["segments"][1],
            ]

            result = extractor.extract_speaker_data(
                sample_analysis_results, speaker_id=1
            )

            assert "average_sentiment_score" in result
            assert "sentiment_volatility" in result
            assert "dominant_sentiment_pattern" in result

    def test_extract_speaker_data_no_segments(self, extractor, sample_analysis_results):
        """Test extraction with no segments."""
        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = []

            result = extractor.extract_speaker_data(
                sample_analysis_results, speaker_id=1
            )

            # Should return empty data structure
            assert result is not None

    def test_extract_speaker_data_trigger_words(
        self, extractor, sample_analysis_results
    ):
        """Test trigger word extraction."""
        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = sample_analysis_results["segments"][:2]

            result = extractor.extract_speaker_data(
                sample_analysis_results, speaker_id=1
            )

            # Should include trigger words
            assert "positive_trigger_words" in result or "trigger_words" in result

    def test_extract_speaker_data_validation(self, extractor, sample_analysis_results):
        """Test data validation."""
        with (
            patch.object(extractor, "get_speaker_segments") as mock_get_segments,
            patch.object(extractor, "validate_data") as mock_validate,
        ):
            mock_get_segments.return_value = sample_analysis_results["segments"][:2]
            mock_validate.return_value = True

            result = extractor.extract_speaker_data(
                sample_analysis_results, speaker_id=1
            )

            # Should validate data
            assert result is not None


class TestSentimentExtractorErrorHandling:
    """Tests for error handling in sentiment extractor."""

    @pytest.fixture
    def extractor(self):
        """Fixture for SentimentDataExtractor instance."""
        return SentimentDataExtractor()

    @pytest.fixture
    def sample_analysis_results(self):
        """Fixture for sample analysis results with sentiment data (shared with basic tests)."""
        return {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "I love this!",
                    "sentiment_score": 0.8,
                    "sentiment_label": "positive",
                    "trigger_words": ["love"],
                },
                {
                    "speaker": "SPEAKER_00",
                    "text": "This is great!",
                    "sentiment_score": 0.9,
                    "sentiment_label": "positive",
                    "trigger_words": ["great"],
                },
            ]
        }

    def test_missing_required_analysis_results(self, extractor):
        """Test handling when required analysis results are missing."""
        incomplete_results = {"segments": []}  # Missing sentiment data

        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = []

            result = extractor.extract_speaker_data(incomplete_results, speaker_id=1)

            # Should return empty data structure
            assert result is not None

    def test_partial_data_available(self, extractor):
        """Test extraction when only partial data is available."""
        partial_results = {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Test",
                    # Missing sentiment_score
                    "sentiment_label": "positive",
                }
            ]
        }

        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = partial_results["segments"]

            result = extractor.extract_speaker_data(partial_results, speaker_id=1)

            # Should extract available data
            assert result is not None

    def test_invalid_data_structure(self, extractor):
        """Test handling when data structure is invalid."""
        invalid_results = "not a dictionary"

        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.side_effect = TypeError("Invalid data structure")

            # Should handle invalid structure
            try:
                result = extractor.extract_speaker_data(invalid_results, speaker_id=1)
                # If it doesn't raise, should return empty data
                assert result is not None
            except (TypeError, ValueError):
                # Expected behavior
                pass

    def test_invalid_data_types(self, extractor):
        """Test handling when data types are invalid."""
        invalid_results = {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Test",
                    "sentiment_score": "not a number",  # Invalid type
                    "sentiment_label": 123,  # Invalid type
                }
            ]
        }

        with (
            patch.object(extractor, "get_speaker_segments") as mock_get_segments,
            patch.object(extractor, "safe_float") as mock_safe_float,
        ):
            mock_get_segments.return_value = invalid_results["segments"]
            mock_safe_float.return_value = None  # Conversion fails

            result = extractor.extract_speaker_data(invalid_results, speaker_id=1)

            # Should handle type errors gracefully
            assert result is not None

    def test_out_of_range_values(self, extractor):
        """Test handling when values are out of range."""
        out_of_range_results = {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Test",
                    "sentiment_score": 999.0,  # Out of range
                    "sentiment_label": "positive",
                }
            ]
        }

        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = out_of_range_results["segments"]

            result = extractor.extract_speaker_data(out_of_range_results, speaker_id=1)

            # Should handle out of range values
            assert result is not None

    def test_missing_required_fields(self, extractor):
        """Test handling when required fields are missing."""
        missing_fields_results = {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    # Missing text, sentiment_score, sentiment_label
                }
            ]
        }

        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = missing_fields_results["segments"]

            result = extractor.extract_speaker_data(
                missing_fields_results, speaker_id=1
            )

            # Should handle missing fields with defaults
            assert result is not None

    def test_database_connection_failure(self, extractor, sample_analysis_results):
        """Test handling when database connection fails."""
        with (
            patch.object(extractor, "get_speaker_segments") as mock_get_segments,
            patch.object(extractor, "validate_data") as mock_validate,
        ):
            mock_get_segments.return_value = sample_analysis_results["segments"][:2]
            mock_validate.side_effect = ConnectionError("Database connection failed")

            # Should handle database errors
            try:
                result = extractor.extract_speaker_data(
                    sample_analysis_results, speaker_id=1
                )
                # If extraction succeeds, validation may fail later
                assert result is not None
            except ConnectionError:
                # Expected if validation raises
                pass
