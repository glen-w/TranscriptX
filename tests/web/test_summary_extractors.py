"""
Tests for summary extractors.
"""

import pytest
from transcriptx.web.summary_extractors import (
    register_extractor,
    get_extractor,
    has_extractor,
)


class TestSummaryExtractors:
    """Tests for summary extractor registry."""
    
    def test_register_and_get_extractor(self):
        """Test registering and retrieving an extractor."""
        def test_extractor(data, summary):
            summary["key_metrics"]["test"] = "value"
        
        register_extractor("test_module", test_extractor)
        
        assert has_extractor("test_module") is True
        retrieved = get_extractor("test_module")
        assert retrieved == test_extractor
        
        # Test extraction
        summary = {"key_metrics": {}, "highlights": []}
        retrieved({}, summary)
        assert summary["key_metrics"]["test"] == "value"
    
    def test_get_nonexistent_extractor(self):
        """Test getting extractor for nonexistent module."""
        assert has_extractor("nonexistent_module") is False
        assert get_extractor("nonexistent_module") is None
    
    def test_extractors_registered(self):
        """Test that all module extractors are registered."""
        expected_modules = [
            "sentiment",
            "emotion",
            "topic_modeling",
            "ner",
            "acts",
            "stats",
            "contagion",
            "tics",
            "interactions",
            "semantic_similarity",
            "semantic_similarity_advanced",
            "entity_sentiment",
            "understandability",
            "temporal_dynamics",
            "qa_analysis",
            "__generic__",
        ]
        
        for module in expected_modules:
            assert has_extractor(module), f"Extractor for {module} should be registered"
    
    def test_sentiment_extractor(self):
        """Test sentiment extractor functionality."""
        extractor = get_extractor("sentiment")
        assert extractor is not None
        
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
        
        summary = {"key_metrics": {}, "highlights": []}
        extractor(data, summary)
        
        assert "Overall Sentiment" in summary["key_metrics"]
        assert "Positive Segments" in summary["key_metrics"]
        assert len(summary["highlights"]) > 0
    
    def test_emotion_extractor(self):
        """Test emotion extractor functionality."""
        extractor = get_extractor("emotion")
        assert extractor is not None
        
        data = {
            "emotions": {
                "joy": [{"text": "happy"}],
                "sadness": [{"text": "sad"}],
            }
        }
        
        summary = {"key_metrics": {}, "highlights": []}
        extractor(data, summary)
        
        assert "Emotions Detected" in summary["key_metrics"]
        assert "Dominant Emotion" in summary["key_metrics"]
    
    def test_generic_extractor(self):
        """Test generic extractor as fallback."""
        extractor = get_extractor("__generic__")
        assert extractor is not None
        
        data = {
            "summary": {"key1": "value1"},
            "statistics": {"count": 42},
            "total": 100,
        }
        
        summary = {"key_metrics": {}, "highlights": []}
        extractor(data, summary)
        
        assert "key1" in summary["key_metrics"]
        assert "count" in summary["key_metrics"]
        assert "Total" in summary["key_metrics"]
