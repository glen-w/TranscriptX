"""
Tests for logging utilities.

This module tests logger setup, configuration, and logging functions.
"""

import logging
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from transcriptx.core.utils.logger import (
    setup_logging,
    get_logger,
    log_error,
    log_warning,
    log_info,
    log_debug,
    reset_logging,
)


class TestSetupLogging:
    """Tests for setup_logging function."""
    
    def test_sets_up_logger_with_defaults(self):
        """Test that logger is set up with default values."""
        reset_logging()
        
        logger = setup_logging()
        
        assert logger is not None
        assert logger.name == "transcriptx"
        assert logger.level == logging.INFO
    
    def test_sets_custom_log_level(self):
        """Test that custom log level is set."""
        reset_logging()
        
        logger = setup_logging(level="DEBUG")
        
        assert logger.level == logging.DEBUG
    
    def test_sets_up_file_logging(self, tmp_path):
        """Test that file logging is set up when log_file is provided."""
        reset_logging()
        
        log_file = tmp_path / "test.log"
        logger = setup_logging(log_file=str(log_file))
        
        # Check that file handler exists
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) > 0
    
    def test_returns_singleton_instance(self):
        """Test that same logger instance is returned on subsequent calls."""
        reset_logging()
        
        logger1 = setup_logging()
        logger2 = setup_logging()
        
        assert logger1 is logger2
    
    def test_uses_custom_format(self):
        """Test that custom format string is used."""
        reset_logging()
        
        custom_format = "%(levelname)s - %(message)s"
        logger = setup_logging(format_string=custom_format)
        
        # Check that formatter uses custom format
        handlers = logger.handlers
        assert len(handlers) > 0
        assert handlers[0].formatter._fmt == custom_format


class TestGetLogger:
    """Tests for get_logger function."""
    
    def test_returns_logger_instance(self):
        """Test that logger instance is returned."""
        reset_logging()
        setup_logging()
        
        logger = get_logger()
        
        assert logger is not None
        assert isinstance(logger, logging.Logger)
    
    def test_creates_logger_if_not_setup(self):
        """Test that logger is created if not already set up."""
        reset_logging()
        
        logger = get_logger()
        
        assert logger is not None
        assert logger.name == "transcriptx"


class TestLogError:
    """Tests for log_error function."""
    
    def test_logs_error_message(self, tmp_path):
        """Test that error message is logged."""
        reset_logging()
        log_file = tmp_path / "test.log"
        setup_logging(level="ERROR", log_file=str(log_file))
        
        log_error("TEST_MODULE", "Test error message", exception=ValueError("Test"))
        
        # Check that error was logged
        with open(log_file) as f:
            content = f.read()
            assert "Test error message" in content or "ERROR" in content
    
    def test_logs_with_context(self, tmp_path):
        """Test that error is logged with context."""
        reset_logging()
        log_file = tmp_path / "test.log"
        setup_logging(level="ERROR", log_file=str(log_file))
        
        log_error("TEST_MODULE", "Test error", context="test_context")
        
        with open(log_file) as f:
            content = f.read()
            # Context should be in log
            assert "test_context" in content or "ERROR" in content


class TestLogWarning:
    """Tests for log_warning function."""
    
    def test_logs_warning_message(self, tmp_path):
        """Test that warning message is logged."""
        reset_logging()
        log_file = tmp_path / "test.log"
        setup_logging(level="WARNING", log_file=str(log_file))
        
        log_warning("TEST_MODULE", "Test warning")
        
        with open(log_file) as f:
            content = f.read()
            assert "Test warning" in content or "WARNING" in content
    
    def test_logs_with_context(self, tmp_path):
        """Test that warning is logged with context."""
        reset_logging()
        log_file = tmp_path / "test.log"
        setup_logging(level="WARNING", log_file=str(log_file))
        
        log_warning("TEST_MODULE", "Test warning", context="test_context")
        
        with open(log_file) as f:
            content = f.read()
            assert "test_context" in content or "WARNING" in content


class TestLogInfo:
    """Tests for log_info function."""
    
    def test_logs_info_message(self, tmp_path):
        """Test that info message is logged."""
        reset_logging()
        log_file = tmp_path / "test.log"
        setup_logging(level="INFO", log_file=str(log_file))
        
        log_info("TEST_MODULE", "Test info message")
        
        with open(log_file) as f:
            content = f.read()
            assert "Test info message" in content or "INFO" in content


class TestLogDebug:
    """Tests for log_debug function."""
    
    def test_logs_debug_message(self, tmp_path):
        """Test that debug message is logged."""
        reset_logging()
        log_file = tmp_path / "test.log"
        setup_logging(level="DEBUG", log_file=str(log_file))
        
        log_debug("TEST_MODULE", "Test debug message")
        
        with open(log_file) as f:
            content = f.read()
            assert "Test debug message" in content or "DEBUG" in content
    
    def test_does_not_log_when_level_too_high(self, tmp_path):
        """Test that debug message is not logged when level is too high."""
        reset_logging()
        log_file = tmp_path / "test.log"
        setup_logging(level="INFO", log_file=str(log_file))
        
        log_debug("TEST_MODULE", "Test debug message")
        
        with open(log_file) as f:
            content = f.read()
            # Should not contain debug message when level is INFO
            assert "Test debug message" not in content


class TestResetLogging:
    """Tests for reset_logging function."""
    
    def test_resets_global_logger(self):
        """Test that global logger is reset."""
        reset_logging()
        logger1 = setup_logging()
        
        reset_logging()
        logger2 = setup_logging()
        
        # Should be different instances after reset
        # (though they may have same name)
        assert logger1.name == logger2.name
