"""
Tests for tic data extractor.

This module tests extraction of verbal tics data from analysis results.
"""

from unittest.mock import MagicMock, patch
import pytest

from transcriptx.core.data_extraction.tic_extractor import TicDataExtractor


class TestTicDataExtractor:
    """Tests for TicDataExtractor."""
    
    @pytest.fixture
    def extractor(self):
        """Fixture for TicDataExtractor instance."""
        return TicDataExtractor()
    
    @pytest.fixture
    def sample_analysis_results(self):
        """Fixture for sample analysis results with tic data."""
        return {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Um, I think that, uh, this is good.",
                    "tics": [
                        {"text": "um", "type": "filler", "context": "beginning"},
                        {"text": "uh", "type": "filler", "context": "middle"}
                    ]
                },
                {
                    "speaker": "SPEAKER_00",
                    "text": "Like, you know, it's fine.",
                    "tics": [
                        {"text": "like", "type": "filler", "context": "beginning"},
                        {"text": "you know", "type": "filler", "context": "middle"}
                    ]
                },
            ]
        }
    
    def test_extract_speaker_data_basic(self, extractor, sample_analysis_results):
        """Test basic speaker data extraction."""
        with patch.object(extractor, 'get_speaker_segments') as mock_get_segments:
            mock_get_segments.return_value = sample_analysis_results["segments"]
            
            result = extractor.extract_speaker_data(sample_analysis_results, speaker_id=1)
            
            assert "tic_frequency" in result
            assert "tic_types" in result
    
    def test_extract_speaker_data_no_segments(self, extractor, sample_analysis_results):
        """Test extraction with no segments."""
        with patch.object(extractor, 'get_speaker_segments') as mock_get_segments:
            mock_get_segments.return_value = []
            
            result = extractor.extract_speaker_data(sample_analysis_results, speaker_id=1)
            
            assert result is not None


class TestTicExtractorErrorHandling:
    """Tests for error handling in tic extractor."""
    
    @pytest.fixture
    def extractor(self):
        """Fixture for TicDataExtractor instance."""
        return TicDataExtractor()
    
    def test_missing_tic_data(self, extractor):
        """Test handling when tic data is missing."""
        incomplete_results = {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Test"
                    # Missing tics
                }
            ]
        }
        
        with patch.object(extractor, 'get_speaker_segments') as mock_get_segments:
            mock_get_segments.return_value = incomplete_results["segments"]
            
            result = extractor.extract_speaker_data(incomplete_results, speaker_id=1)
            
            # Should handle missing tics
            assert result is not None
    
    def test_invalid_tic_structure(self, extractor):
        """Test handling when tic structure is invalid."""
        invalid_results = {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Test",
                    "tics": "not a list"  # Invalid type
                }
            ]
        }
        
        with patch.object(extractor, 'get_speaker_segments') as mock_get_segments:
            mock_get_segments.return_value = invalid_results["segments"]
            
            result = extractor.extract_speaker_data(invalid_results, speaker_id=1)
            
            # Should handle invalid structure
            assert result is not None
