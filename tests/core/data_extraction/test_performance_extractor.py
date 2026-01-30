"""
Tests for performance data extractor.

This module tests extraction of performance data from analysis results.
"""

from unittest.mock import MagicMock, patch
import pytest

from transcriptx.core.data_extraction.performance_extractor import PerformanceDataExtractor


class TestPerformanceDataExtractor:
    """Tests for PerformanceDataExtractor."""
    
    @pytest.fixture
    def extractor(self):
        """Fixture for PerformanceDataExtractor instance."""
        return PerformanceDataExtractor()
    
    @pytest.fixture
    def sample_analysis_results(self):
        """Fixture for sample analysis results with performance data."""
        return {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "This is a test sentence.",
                    "duration": 2.5,
                    "participation": {"turn_count": 1, "word_count": 5}
                },
                {
                    "speaker": "SPEAKER_00",
                    "text": "Another sentence here.",
                    "duration": 3.0,
                    "participation": {"turn_count": 2, "word_count": 3}
                },
            ]
        }
    
    def test_extract_speaker_data_basic(self, extractor, sample_analysis_results):
        """Test basic speaker data extraction."""
        with patch.object(extractor, 'get_speaker_segments') as mock_get_segments:
            mock_get_segments.return_value = sample_analysis_results["segments"]
            
            result = extractor.extract_speaker_data(sample_analysis_results, speaker_id=1)
            
            assert "speaking_style" in result
            assert "performance_metrics" in result
    
    def test_extract_speaker_data_no_segments(self, extractor, sample_analysis_results):
        """Test extraction with no segments."""
        with patch.object(extractor, 'get_speaker_segments') as mock_get_segments:
            mock_get_segments.return_value = []
            
            result = extractor.extract_speaker_data(sample_analysis_results, speaker_id=1)
            
            assert result is not None


class TestPerformanceExtractorErrorHandling:
    """Tests for error handling in performance extractor."""
    
    @pytest.fixture
    def extractor(self):
        """Fixture for PerformanceDataExtractor instance."""
        return PerformanceDataExtractor()
    
    def test_missing_performance_data(self, extractor):
        """Test handling when performance data is missing."""
        incomplete_results = {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Test"
                    # Missing duration, participation
                }
            ]
        }
        
        with patch.object(extractor, 'get_speaker_segments') as mock_get_segments:
            mock_get_segments.return_value = incomplete_results["segments"]
            
            result = extractor.extract_speaker_data(incomplete_results, speaker_id=1)
            
            # Should handle missing data with defaults
            assert result is not None
    
    def test_invalid_duration_values(self, extractor):
        """Test handling when duration values are invalid."""
        invalid_results = {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Test",
                    "duration": "not a number"  # Invalid type
                }
            ]
        }
        
        with patch.object(extractor, 'get_speaker_segments') as mock_get_segments:
            mock_get_segments.return_value = invalid_results["segments"]
            
            result = extractor.extract_speaker_data(invalid_results, speaker_id=1)
            
            # Should handle invalid duration
            assert result is not None
