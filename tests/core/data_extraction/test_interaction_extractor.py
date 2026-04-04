"""
Tests for interaction data extractor.

This module tests extraction of interaction data from analysis results.
"""

from unittest.mock import patch
import pytest

from transcriptx.core.data_extraction.interaction_extractor import (
    InteractionDataExtractor,
)


class TestInteractionDataExtractor:
    """Tests for InteractionDataExtractor."""

    @pytest.fixture
    def extractor(self):
        """Fixture for InteractionDataExtractor instance."""
        return InteractionDataExtractor()

    @pytest.fixture
    def sample_analysis_results(self):
        """Fixture for sample analysis results with interaction data."""
        return {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "I think we should...",
                    "interactions": [
                        {
                            "type": "interruption",
                            "target_speaker": "SPEAKER_01",
                            "duration": 0.5,
                        }
                    ],
                },
                {
                    "speaker": "SPEAKER_01",
                    "text": "Yes, I agree.",
                    "interactions": [
                        {
                            "type": "response",
                            "target_speaker": "SPEAKER_00",
                            "duration": 1.0,
                        }
                    ],
                },
            ]
        }

    def test_extract_speaker_data_basic(self, extractor, sample_analysis_results):
        """Test basic speaker data extraction."""
        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = [sample_analysis_results["segments"][0]]

            result = extractor.extract_speaker_data(
                sample_analysis_results, speaker_id=1
            )

            assert "interaction_style" in result
            assert "interruption_patterns" in result

    def test_extract_speaker_data_no_segments(self, extractor, sample_analysis_results):
        """Test extraction with no segments."""
        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = []

            result = extractor.extract_speaker_data(
                sample_analysis_results, speaker_id=1
            )

            assert result is not None


class TestInteractionExtractorErrorHandling:
    """Tests for error handling in interaction extractor."""

    @pytest.fixture
    def extractor(self):
        """Fixture for InteractionDataExtractor instance."""
        return InteractionDataExtractor()

    def test_missing_interaction_data(self, extractor):
        """Test handling when interaction data is missing."""
        incomplete_results = {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Test",
                    # Missing interactions
                }
            ]
        }

        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = incomplete_results["segments"]

            result = extractor.extract_speaker_data(incomplete_results, speaker_id=1)

            # Should handle missing interactions
            assert result is not None

    def test_invalid_interaction_structure(self, extractor):
        """Test handling when interaction structure is invalid."""
        invalid_results = {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Test",
                    "interactions": "not a list",  # Invalid type
                }
            ]
        }

        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = invalid_results["segments"]

            result = extractor.extract_speaker_data(invalid_results, speaker_id=1)

            # Should handle invalid structure
            assert result is not None
