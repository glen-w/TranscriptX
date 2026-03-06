"""
Tests for emotion data extractor.

This module tests extraction of emotion data from analysis results.
"""

from unittest.mock import patch
import pytest

from transcriptx.core.data_extraction.emotion_extractor import EmotionDataExtractor


class TestEmotionDataExtractor:
    """Tests for EmotionDataExtractor."""

    @pytest.fixture
    def extractor(self):
        """Fixture for EmotionDataExtractor instance."""
        return EmotionDataExtractor()

    @pytest.fixture
    def sample_analysis_results(self):
        """Fixture for sample analysis results with emotion data."""
        return {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "I'm so happy!",
                    "dominant_emotion": "joy",
                    "emotion_scores": {"joy": 0.9, "sadness": 0.1},
                },
                {
                    "speaker": "SPEAKER_00",
                    "text": "This is exciting!",
                    "dominant_emotion": "joy",
                    "emotion_scores": {"joy": 0.8, "fear": 0.2},
                },
                {
                    "speaker": "SPEAKER_01",
                    "text": "I'm worried about this.",
                    "dominant_emotion": "fear",
                    "emotion_scores": {"fear": 0.7, "joy": 0.3},
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

            assert "dominant_emotion" in result
            assert "emotion_distribution" in result

    def test_extract_speaker_data_no_segments(self, extractor, sample_analysis_results):
        """Test extraction with no segments."""
        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = []

            result = extractor.extract_speaker_data(
                sample_analysis_results, speaker_id=1
            )

            assert result is not None

    def test_extract_speaker_data_emotion_stability(
        self, extractor, sample_analysis_results
    ):
        """Test emotion stability calculation."""
        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = sample_analysis_results["segments"][:2]

            result = extractor.extract_speaker_data(
                sample_analysis_results, speaker_id=1
            )

            assert "emotional_stability" in result or "stability" in result


class TestEmotionExtractorErrorHandling:
    """Tests for error handling in emotion extractor."""

    @pytest.fixture
    def extractor(self):
        """Fixture for EmotionDataExtractor instance."""
        return EmotionDataExtractor()

    def test_missing_emotion_data(self, extractor):
        """Test handling when emotion data is missing."""
        incomplete_results = {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Test",
                    # Missing emotion data
                }
            ]
        }

        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = incomplete_results["segments"]

            result = extractor.extract_speaker_data(incomplete_results, speaker_id=1)

            # Should handle missing data gracefully
            assert result is not None

    def test_invalid_emotion_scores(self, extractor):
        """Test handling when emotion scores are invalid."""
        invalid_results = {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Test",
                    "emotion_scores": "not a dict",  # Invalid type
                }
            ]
        }

        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = invalid_results["segments"]

            result = extractor.extract_speaker_data(invalid_results, speaker_id=1)

            # Should handle invalid scores
            assert result is not None
