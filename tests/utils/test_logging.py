"""
Tests for logging utilities.

This module tests logging setup, log levels, and log formatting.
"""

from unittest.mock import MagicMock, patch


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
        with patch(
            "transcriptx.core.utils.logger.logging.getLogger"
        ) as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            setup_logging(level="DEBUG")
            mock_get_logger.assert_called()
            assert mock_logger.addHandler.called

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
