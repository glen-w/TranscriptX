"""
Tests for speaker profile aggregator.

This module tests SpeakerProfileAggregator.
"""

from unittest.mock import MagicMock, patch
import pytest

from transcriptx.core.integration.profile_aggregator import SpeakerProfileAggregator


class TestSpeakerProfileAggregator:
    """Tests for SpeakerProfileAggregator."""
    
    @pytest.fixture
    def aggregator(self):
        """Fixture for SpeakerProfileAggregator instance."""
        mock_session = MagicMock()
        return SpeakerProfileAggregator(database_session=mock_session)
    
    def test_aggregator_initialization(self, aggregator):
        """Test aggregator initialization."""
        assert aggregator is not None
        assert hasattr(aggregator, 'profile_types')
        assert hasattr(aggregator, 'session')
    
    def test_aggregate_profiles(self, aggregator):
        """Test aggregating profiles for a conversation."""
        with patch.object(aggregator, '_get_conversation_speakers') as mock_get_speakers, \
             patch.object(aggregator, 'aggregate_speaker_profile') as mock_aggregate:
            
            mock_speaker = MagicMock()
            mock_speaker.id = 1
            mock_get_speakers.return_value = [mock_speaker]
            mock_aggregate.return_value = {"status": "success"}
            
            result = aggregator.aggregate_profiles(conversation_id=1)
            
            assert "conversation_id" in result
            assert "speakers_aggregated" in result
    
    def test_aggregate_speaker_profile(self, aggregator):
        """Test aggregating profile for a single speaker."""
        with patch.object(aggregator, '_get_speaker_profiles') as mock_get_profiles:
            mock_get_profiles.return_value = {}
            
            result = aggregator.aggregate_speaker_profile(speaker_id=1)
            
            assert result is not None
