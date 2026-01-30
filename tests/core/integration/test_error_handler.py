"""
Tests for integration error handler.

This module tests IntegrationErrorHandler.
"""

from unittest.mock import MagicMock, patch
import pytest

from transcriptx.core.integration.error_handler import IntegrationErrorHandler, IntegrationError


class TestIntegrationErrorHandler:
    """Tests for IntegrationErrorHandler."""
    
    @pytest.fixture
    def handler(self):
        """Fixture for IntegrationErrorHandler instance."""
        return IntegrationErrorHandler()
    
    def test_handler_initialization(self, handler):
        """Test handler initialization."""
        assert handler is not None
        assert hasattr(handler, 'recovery_strategies')
        assert hasattr(handler, 'error_history')
    
    def test_handle_error_basic(self, handler):
        """Test basic error handling."""
        error = ValueError("Test error")
        result = handler.handle_error(error, context="test_context")
        
        assert "timestamp" in result
        assert "context" in result
        assert "error_type" in result
        assert "message" in result
        assert result["context"] == "test_context"
    
    def test_handle_error_with_recovery(self, handler):
        """Test error handling with recovery strategy."""
        error = ValueError("Data validation error")
        
        with patch.object(handler, '_classify_error', return_value='data_validation'):
            result = handler.handle_error(error, context="test")
            
            assert "recovery_attempted" in result
            assert result["recovery_attempted"] is True
    
    def test_error_history(self, handler):
        """Test that errors are stored in history."""
        error = ValueError("Test error")
        handler.handle_error(error, context="test")
        
        assert len(handler.error_history) > 0
        assert handler.error_history[-1]["context"] == "test"


class TestIntegrationError:
    """Tests for IntegrationError exception."""
    
    def test_error_creation(self):
        """Test creating IntegrationError."""
        error = IntegrationError("Test error", error_type="test", context={"key": "value"})
        
        assert str(error) == "Test error"
        assert error.error_type == "test"
        assert error.context == {"key": "value"}
        assert error.timestamp is not None
