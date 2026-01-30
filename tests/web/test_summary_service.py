"""
Tests for summary service.
"""

import pytest
from unittest.mock import patch, MagicMock

from transcriptx.web.services.summary_service import SummaryService


class TestSummaryService:
    """Tests for SummaryService."""
    
    def test_extract_analysis_summary_no_data(self):
        """Test extracting summary when no data provided."""
        result = SummaryService.extract_analysis_summary("sentiment", None)
        
        assert result["has_data"] is False
        assert result["key_metrics"] == {}
        assert result["highlights"] == []
    
    @patch('transcriptx.web.services.summary_service.get_extractor')
    def test_extract_analysis_summary_with_extractor(self, mock_get_extractor):
        """Test extracting summary with registered extractor."""
        def mock_extractor(data, summary):
            summary["key_metrics"]["test"] = "value"
            summary["highlights"].append("Test highlight")
        
        mock_get_extractor.return_value = mock_extractor
        
        data = {"test": "data"}
        result = SummaryService.extract_analysis_summary("sentiment", data)
        
        assert result["has_data"] is True
        assert result["key_metrics"]["test"] == "value"
        assert len(result["highlights"]) == 1
    
    @patch('transcriptx.web.services.summary_service.get_extractor')
    def test_extract_analysis_summary_no_extractor_fallback(self, mock_get_extractor):
        """Test extracting summary falls back to generic extractor."""
        # No specific extractor
        mock_get_extractor.return_value = None
        
        # But generic extractor exists
        def generic_extractor(data, summary):
            summary["key_metrics"]["generic"] = True
        
        with patch('transcriptx.web.services.summary_service.get_extractor') as mock_get:
            # First call returns None (no specific extractor)
            # Second call returns generic extractor
            mock_get.side_effect = [None, generic_extractor]
            
            data = {"summary": {"test": "value"}}
            result = SummaryService.extract_analysis_summary("unknown_module", data)
            
            # Should use generic extractor
            assert result["has_data"] is True
    
    @patch('transcriptx.web.services.summary_service.get_extractor')
    def test_extract_analysis_summary_extractor_exception(self, mock_get_extractor):
        """Test that exceptions in extractor are handled gracefully."""
        def failing_extractor(data, summary):
            raise ValueError("Test error")
        
        mock_get_extractor.return_value = failing_extractor
        
        data = {"test": "data"}
        result = SummaryService.extract_analysis_summary("sentiment", data)
        
        # Should handle error and mark as no data
        assert result["has_data"] is False
    
    def test_extract_analysis_summary_real_sentiment(self):
        """Test extracting summary with real sentiment extractor."""
        data = {
            "global_stats": {
                "compound_mean": 0.5,
                "positive_count": 10,
                "negative_count": 5,
                "neutral_count": 15,
            },
            "speaker_stats": {
                "SPEAKER_00": {"compound_mean": 0.8},
                "SPEAKER_01": {"compound_mean": -0.2},
            }
        }
        
        result = SummaryService.extract_analysis_summary("sentiment", data)
        
        assert result["has_data"] is True
        assert "Overall Sentiment" in result["key_metrics"]
        assert "Positive Segments" in result["key_metrics"]
        assert len(result["highlights"]) > 0
