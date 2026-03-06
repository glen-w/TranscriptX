"""
Tests for semantic similarity data extractor.

This module tests extraction of semantic similarity data from analysis results.
"""

import pytest

from transcriptx.core.data_extraction.semantic_extractor import SemanticDataExtractor


class TestSemanticDataExtractor:
    """Tests for SemanticDataExtractor."""

    @pytest.fixture
    def extractor(self):
        """Fixture for SemanticDataExtractor instance."""
        return SemanticDataExtractor()

    @pytest.fixture
    def sample_analysis_results(self):
        """Fixture for sample analysis results with semantic similarity data."""
        return {
            "repetitions": [
                {
                    "segment1": 0,
                    "segment2": 1,
                    "similarity": 0.95,
                    "speaker": "SPEAKER_00",
                }
            ],
            "similarity_scores": {"SPEAKER_00": [0.8, 0.9, 0.7]},
            "speaker_repetitions": {
                "SPEAKER_00": [{"type": "exact", "similarity": 0.95}]
            },
        }

    def test_extract_data_basic(self, extractor, sample_analysis_results):
        """Test basic data extraction."""
        result = extractor.extract_data(
            sample_analysis_results, speaker_id="SPEAKER_00"
        )

        assert "repetitions" in result
        assert "similarity_scores" in result

    def test_extract_data_no_repetitions(self, extractor):
        """Test extraction with no repetitions."""
        analysis_results = {
            "repetitions": [],
            "similarity_scores": {},
            "speaker_repetitions": {},
        }

        result = extractor.extract_data(analysis_results, speaker_id="SPEAKER_00")

        assert result is not None
        assert "repetitions" in result


class TestSemanticExtractorErrorHandling:
    """Tests for error handling in semantic extractor."""

    @pytest.fixture
    def extractor(self):
        """Fixture for SemanticDataExtractor instance."""
        return SemanticDataExtractor()

    def test_missing_semantic_data(self, extractor):
        """Test handling when semantic similarity data is missing."""
        incomplete_results = {
            "repetitions": [],
            "similarity_scores": {},
            "speaker_repetitions": {},
        }

        result = extractor.extract_data(incomplete_results, speaker_id="SPEAKER_00")

        # Should handle missing data
        assert result is not None
        assert "repetitions" in result

    def test_invalid_similarity_scores(self, extractor):
        """Test handling when similarity scores are invalid."""
        invalid_results = {
            "repetitions": [],
            "similarity_scores": "not a dict",  # Invalid type
            "speaker_repetitions": {},
        }

        result = extractor.extract_data(invalid_results, speaker_id="SPEAKER_00")

        # Should handle invalid scores
        assert result is not None
