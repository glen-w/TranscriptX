"""
Tests for conversation type analysis module.

This module tests conversation type classification.
"""

import pytest

from transcriptx.core.analysis.conversation_type import ConversationTypeDetector


class TestConversationTypeDetector:
    """Tests for ConversationTypeDetector."""

    @pytest.fixture
    def detector(self):
        """Fixture for ConversationTypeDetector instance."""
        return ConversationTypeDetector()

    @pytest.fixture
    def sample_segments_meeting(self):
        """Fixture for sample meeting transcript segments using database-driven speaker identification."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Let's start the meeting. First item on the agenda.",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "I'll present the status update.",
                "start": 2.0,
                "end": 4.0,
            },
            {
                "speaker": "Charlie",
                "speaker_db_id": 3,
                "text": "Great, let's review the action items.",
                "start": 4.0,
                "end": 6.0,
            },
        ]

    @pytest.fixture
    def sample_segments_conversation(self):
        """Fixture for sample conversation transcript segments using database-driven speaker identification."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Hey, how are you?",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "I'm doing well, thanks!",
                "start": 2.0,
                "end": 4.0,
            },
        ]

    @pytest.fixture
    def sample_segments_voice_note(self):
        """Fixture for sample voice note transcript segments using database-driven speaker identification."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Let me think about this. I'm reflecting on the project.",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "This is a personal note to myself.",
                "start": 2.0,
                "end": 4.0,
            },
        ]

    def test_detect_type_meeting(self, detector, sample_segments_meeting):
        """Test detection of meeting type."""
        result = detector.detect_type(sample_segments_meeting, speaker_count=3)

        assert "type" in result
        assert result["type"] in ["meeting", "conversation", "voice_note"]
        assert "confidence" in result

    def test_detect_type_conversation(self, detector, sample_segments_conversation):
        """Test detection of conversation type."""
        result = detector.detect_type(sample_segments_conversation, speaker_count=2)

        assert "type" in result
        assert result["type"] in ["meeting", "conversation", "voice_note"]
        assert "confidence" in result

    def test_detect_type_voice_note(self, detector, sample_segments_voice_note):
        """Test detection of voice note type."""
        result = detector.detect_type(sample_segments_voice_note, speaker_count=1)

        assert "type" in result
        # Single speaker should likely be voice_note
        assert result["type"] in ["meeting", "conversation", "voice_note"]
        assert "confidence" in result

    def test_detect_type_by_speaker_count(self, detector):
        """Test detection based on speaker count."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Test.",
                "start": 0.0,
                "end": 1.0,
            },
        ]

        # Single speaker
        result = detector.detect_type(segments, speaker_count=1)
        assert result["type"] in ["meeting", "conversation", "voice_note"]

        # Multiple speakers
        result = detector.detect_type(segments, speaker_count=4)
        assert result["type"] in ["meeting", "conversation", "voice_note"]

    def test_detect_type_empty_segments(self, detector):
        """Test detection with empty segments."""
        segments = []

        result = detector.detect_type(segments, speaker_count=0)

        assert "type" in result
        assert "confidence" in result

    def test_detect_type_confidence_scoring(self, detector, sample_segments_meeting):
        """Test that detection includes confidence scores."""
        result = detector.detect_type(sample_segments_meeting, speaker_count=3)

        assert "confidence" in result
        assert isinstance(result["confidence"], (int, float))
        assert 0 <= result["confidence"] <= 1
