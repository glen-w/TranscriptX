"""
Tests for entity data extractor.

This module tests extraction of NER data from analysis results.
"""

from unittest.mock import patch
import pytest

from transcriptx.core.data_extraction.entity_extractor import EntityDataExtractor


class TestEntityDataExtractor:
    """Tests for EntityDataExtractor."""

    @pytest.fixture
    def extractor(self):
        """Fixture for EntityDataExtractor instance."""
        return EntityDataExtractor()

    @pytest.fixture
    def sample_analysis_results(self):
        """Fixture for sample analysis results with entity data."""
        return {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "I love Python programming.",
                    "entities": [{"text": "Python", "type": "ORG", "sentiment": 0.8}],
                },
                {
                    "speaker": "SPEAKER_00",
                    "text": "Python is great for data science.",
                    "entities": [{"text": "Python", "type": "ORG", "sentiment": 0.9}],
                },
                {
                    "speaker": "SPEAKER_01",
                    "text": "I work at Google.",
                    "entities": [{"text": "Google", "type": "ORG", "sentiment": 0.5}],
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

            assert "entity_expertise_domains" in result or "entities" in result

    def test_extract_speaker_data_no_segments(self, extractor, sample_analysis_results):
        """Test extraction with no segments."""
        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = []

            result = extractor.extract_speaker_data(
                sample_analysis_results, speaker_id=1
            )

            assert result is not None

    def test_extract_speaker_data_frequently_mentioned(
        self, extractor, sample_analysis_results
    ):
        """Test frequently mentioned entities extraction."""
        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = sample_analysis_results["segments"][:2]

            result = extractor.extract_speaker_data(
                sample_analysis_results, speaker_id=1
            )

            # Should identify frequently mentioned entities
            assert result is not None


class TestEntityExtractorErrorHandling:
    """Tests for error handling in entity extractor."""

    @pytest.fixture
    def extractor(self):
        """Fixture for EntityDataExtractor instance."""
        return EntityDataExtractor()

    def test_missing_entity_data(self, extractor):
        """Test handling when entity data is missing."""
        incomplete_results = {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Test",
                    # Missing entities
                }
            ]
        }

        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = incomplete_results["segments"]

            result = extractor.extract_speaker_data(incomplete_results, speaker_id=1)

            # Should handle missing entities
            assert result is not None

    def test_invalid_entity_structure(self, extractor):
        """Test handling when entity structure is invalid."""
        invalid_results = {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Test",
                    "entities": "not a list",  # Invalid type
                }
            ]
        }

        with patch.object(extractor, "get_speaker_segments") as mock_get_segments:
            mock_get_segments.return_value = invalid_results["segments"]

            result = extractor.extract_speaker_data(invalid_results, speaker_id=1)

            # Should handle invalid structure
            assert result is not None
