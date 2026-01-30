"""
Tests for persistence service.

This module tests PersistenceService.
"""

from unittest.mock import MagicMock, patch
import pytest

from transcriptx.core.integration.persistence_service import PersistenceService


class TestPersistenceService:
    """Tests for PersistenceService."""
    
    @pytest.fixture
    def service(self):
        """Fixture for PersistenceService instance."""
        mock_session = MagicMock()
        return PersistenceService(database_session=mock_session)
    
    def test_service_initialization(self, service):
        """Test service initialization."""
        assert service is not None
        assert hasattr(service, 'profile_models')
        assert hasattr(service, 'session')
    
    def test_store_speaker_data_basic(self, service):
        """Test storing speaker data."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None  # No existing profile
        service.session.query.return_value = mock_query
        
        data = {"average_sentiment_score": 0.8}
        result = service.store_speaker_data("sentiment", speaker_id=1, data=data)
        
        assert result is True
    
    def test_store_speaker_data_invalid_type(self, service):
        """Test storing data with invalid analysis type."""
        with pytest.raises(ValueError, match="Invalid analysis type"):
            service.store_speaker_data("invalid_type", speaker_id=1, data={})
    
    def test_store_speaker_data_no_session(self):
        """Test storing data without database session."""
        service = PersistenceService(database_session=None)
        
        result = service.store_speaker_data("sentiment", speaker_id=1, data={})
        
        assert result is False
    
    def test_store_speaker_data_update_existing(self, service):
        """Test updating existing profile."""
        mock_profile = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_profile
        service.session.query.return_value = mock_query
        
        data = {"average_sentiment_score": 0.9}
        result = service.store_speaker_data("sentiment", speaker_id=1, data=data)
        
        assert result is True
