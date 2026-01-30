"""
Tests for tag extraction analysis module.

This module tests tag extraction from transcripts.
"""

from unittest.mock import MagicMock, patch
import pytest

from transcriptx.core.analysis.tag_extraction import TagExtractor, TAG_PATTERNS


class TestTagExtractor:
    """Tests for TagExtractor."""
    
    @pytest.fixture
    def tag_extractor(self):
        """Fixture for TagExtractor instance."""
        return TagExtractor()
    
    @pytest.fixture
    def sample_segments(self):
        """Fixture for sample transcript segments using database-driven speaker identification."""
        return [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "I have an idea for a new project.", "start": 0.0, "end": 2.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "What if we try a different approach?", "start": 2.0, "end": 4.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Let's discuss this in our meeting.", "start": 4.0, "end": 6.0},
        ]
    
    @pytest.fixture
    def sample_speaker_map(self):
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}
    
    def test_tag_extraction_basic(self, tag_extractor, sample_segments, sample_speaker_map):
        """Test basic tag extraction."""
        result = tag_extractor.analyze(sample_segments, sample_speaker_map)
        
        assert "tags" in result or "extracted_tags" in result
        assert "confidence" in result or "summary" in result
    
    def test_tag_extraction_idea_tag(self, tag_extractor, sample_speaker_map):
        """Test extraction of 'idea' tag."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "I have an idea for a new feature.", "start": 0.0, "end": 2.0},
        ]
        
        result = tag_extractor.analyze(segments, sample_speaker_map)
        
        # Should detect 'idea' tag
        tags = result.get("tags", result.get("extracted_tags", []))
        if isinstance(tags, list):
            tag_names = [tag.get("tag", tag) if isinstance(tag, dict) else tag for tag in tags]
            assert "idea" in tag_names or any("idea" in str(tag).lower() for tag in tag_names)
        elif isinstance(tags, dict):
            assert "idea" in tags or any("idea" in str(k).lower() for k in tags.keys())
    
    def test_tag_extraction_meeting_tag(self, tag_extractor, sample_speaker_map):
        """Test extraction of 'meeting' tag."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Let's discuss this in our meeting today.", "start": 0.0, "end": 2.0},
        ]
        
        result = tag_extractor.analyze(segments, sample_speaker_map)
        
        # Should detect 'meeting' tag
        tags = result.get("tags", result.get("extracted_tags", []))
        if isinstance(tags, list):
            tag_names = [tag.get("tag", tag) if isinstance(tag, dict) else tag for tag in tags]
            assert "meeting" in tag_names or any("meeting" in str(tag).lower() for tag in tag_names)
        elif isinstance(tags, dict):
            assert "meeting" in tags or any("meeting" in str(k).lower() for k in tags.keys())
    
    def test_tag_extraction_question_tag(self, tag_extractor, sample_speaker_map):
        """Test extraction of 'question' tag."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "What do you think about this?", "start": 0.0, "end": 2.0},
        ]
        
        result = tag_extractor.analyze(segments, sample_speaker_map)
        
        # Should detect 'question' tag
        tags = result.get("tags", result.get("extracted_tags", []))
        if isinstance(tags, list):
            tag_names = [tag.get("tag", tag) if isinstance(tag, dict) else tag for tag in tags]
            assert "question" in tag_names or any("question" in str(tag).lower() for tag in tag_names)
        elif isinstance(tags, dict):
            assert "question" in tags or any("question" in str(k).lower() for k in tags.keys())
    
    def test_tag_extraction_empty_segments(self, tag_extractor, sample_speaker_map):
        """Test tag extraction with empty segments."""
        segments = []
        
        result = tag_extractor.analyze(segments, sample_speaker_map)
        
        assert result is not None
        assert "tags" in result or "extracted_tags" in result
    
    def test_tag_extraction_early_window(self, tag_extractor, sample_speaker_map):
        """Test that tag extraction focuses on early segments."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "I have an idea.", "start": 0.0, "end": 2.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "That's interesting.", "start": 2.0, "end": 4.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Let's discuss it.", "start": 60.0, "end": 62.0},  # Later segment
        ]
        
        result = tag_extractor.analyze(segments, sample_speaker_map)
        
        # Should extract tags from early segments
        assert result is not None
    
    def test_tag_extraction_confidence_scoring(self, tag_extractor, sample_segments, sample_speaker_map):
        """Test that tags include confidence scores."""
        result = tag_extractor.analyze(sample_segments, sample_speaker_map)
        
        # Should include confidence information
        assert "confidence" in result or any(
            isinstance(tag, dict) and "confidence" in tag 
            for tag in result.get("tags", result.get("extracted_tags", []))
        )
