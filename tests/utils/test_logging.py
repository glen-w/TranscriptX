"""
Tests for logging utilities.

This module tests logging setup, log levels, and log formatting.
"""

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.utils.logger import get_logger, setup_logging


class TestLogging:
    """Tests for logging utilities."""
    
    def test_get_logger(self):
        """Test getting logger instance."""
        logger = get_logger()
        
        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
    
    def test_setup_logging(self):
        """Test setting up logging."""
        with patch('transcriptx.core.utils.logger.logging.basicConfig') as mock_basic:
            setup_logging(level="DEBUG")
            
            # Should configure logging
            assert mock_basic.called
    
    def test_logger_methods(self):
        """Test logger methods."""
        logger = get_logger()
        
        # Should be able to call logging methods
        logger.debug("Test debug message")
        logger.info("Test info message")
        logger.warning("Test warning message")
        logger.error("Test error message")
        
        # Should not raise exceptions
        assert True
