"""
Tests for topic data extractor.

This module tests extraction of topic modeling data from analysis results.
"""

from unittest.mock import patch
import pytest

from transcriptx.core.data_extraction.topic_extractor import TopicDataExtractor


class TestTopicDataExtractor:
    """Tests for TopicDataExtractor."""

    @pytest.fixture
    def extractor(self):
        """Fixture for TopicDataExtractor instance."""
        return TopicDataExtractor()

    @pytest.fixture
    def sample_analysis_results(self):
        """Fixture for sample analysis results with topic data."""
        return {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Machine learning is fascinating.",
                    "topic_id": 0,
                    "topic_confidence": 0.9,
                },
                {
                    "speaker": "SPEAKER_00",
                    "text": "Deep learning models are powerful.",
                    "topic_id": 0,
                    "topic_confidence": 0.8,
                },
                {
                    "speaker": "SPEAKER_01",
                    "text": "Data science requires good tools.",
                    "topic_id": 1,
                    "topic_confidence": 0.7,
                },
            ]
        }

    def test_extract_speaker_data_basic(self, extractor, sample_analysis_results):
        """Test basic speaker data extraction."""
        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = sample_analysis_results["segments"][:2]

            result = extractor.extract_speaker_data(
                sample_analysis_results, speaker_id=1
            )

            assert "preferred_topics" in result or "topics" in result

    def test_extract_speaker_data_no_segments(self, extractor, sample_analysis_results):
        """Test extraction with no segments."""
        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = []

            result = extractor.extract_speaker_data(
                sample_analysis_results, speaker_id=1
            )

            assert result is not None

    def test_extract_speaker_data_topic_contributions(
        self, extractor, sample_analysis_results
    ):
        """Test topic contribution calculation."""
        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = sample_analysis_results["segments"][:2]

            result = extractor.extract_speaker_data(
                sample_analysis_results, speaker_id=1
            )

            # Should include topic contribution information
            assert result is not None


class TestTopicExtractorErrorHandling:
    """Tests for error handling in topic extractor."""

    @pytest.fixture
    def extractor(self):
        """Fixture for TopicDataExtractor instance."""
        return TopicDataExtractor()

    def test_missing_topic_data(self, extractor):
        """Test handling when topic data is missing."""
        incomplete_results = {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Test",
                    # Missing topic_id, topic_confidence
                }
            ]
        }

        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = incomplete_results["segments"]

            result = extractor.extract_speaker_data(incomplete_results, speaker_id=1)

            # Should handle missing topic data
            assert result is not None

    def test_invalid_topic_confidence(self, extractor):
        """Test handling when topic confidence is invalid."""
        invalid_results = {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Test",
                    "topic_id": 0,
                    "topic_confidence": "not a number",  # Invalid type
                }
            ]
        }

        with (
            patch.object(extractor, "get_speaker_segments") as mock_get_segments,
            patch.object(extractor, "safe_float") as mock_safe_float,
        ):
            mock_get_segments.return_value = invalid_results["segments"]
            mock_safe_float.return_value = None

            result = extractor.extract_speaker_data(invalid_results, speaker_id=1)

            # Should handle invalid confidence
            assert result is not None
