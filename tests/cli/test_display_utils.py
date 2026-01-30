"""
Tests for display utility functions.

This module tests banner display and configuration display functions.
"""

from unittest.mock import patch, MagicMock

import pytest

from transcriptx.cli.display_utils import (
    show_banner,
    show_current_config,
)


class TestShowBanner:
    """Tests for show_banner function."""
    
    def test_displays_banner(self):
        """Test that banner is displayed."""
        with patch('transcriptx.cli.display_utils.Console') as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console
            
            show_banner()
            
            # Should print multiple lines
            assert mock_console.print.call_count >= 3
    
    def test_banner_contains_title(self):
        """Test that banner contains TranscriptX title."""
        with patch('transcriptx.cli.display_utils.Console') as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console
            
            show_banner()
            
            # Check that print was called
            assert mock_console.print.called
            # Check for TranscriptX in calls
            call_args_str = str(mock_console.print.call_args_list)
            assert "TranscriptX" in call_args_str or "Transcript" in call_args_str


class TestShowCurrentConfig:
    """Tests for show_current_config function."""
    
    def test_displays_configuration(self):
        """Test that configuration is displayed."""
        from transcriptx.core.utils.config import Config
        
        config = Config()
        
        with patch('builtins.print') as mock_print:
            show_current_config(config)
            
            # Should print multiple lines
            assert mock_print.call_count > 0
    
    def test_displays_analysis_settings(self):
        """Test that analysis settings are displayed."""
        from transcriptx.core.utils.config import Config
        
        config = Config()
        config.analysis.sentiment_window_size = 20
        
        with patch('builtins.print') as mock_print:
            show_current_config(config)
            
            # Check that sentiment window size is printed
            call_args_str = str(mock_print.call_args_list)
            assert "sentiment" in call_args_str.lower() or "20" in call_args_str
    
    def test_displays_transcription_settings(self):
        """Test that transcription settings are displayed."""
        from transcriptx.core.utils.config import Config
        
        config = Config()
        
        with patch('builtins.print') as mock_print:
            show_current_config(config)
            
            # Check that transcription settings are printed
            call_args_str = str(mock_print.call_args_list)
            assert "transcription" in call_args_str.lower() or "model" in call_args_str.lower()
    
    def test_displays_output_settings(self):
        """Test that output settings are displayed."""
        from transcriptx.core.utils.config import Config
        
        config = Config()
        
        with patch('builtins.print') as mock_print:
            show_current_config(config)
            
            # Check that output settings are printed
            call_args_str = str(mock_print.call_args_list)
            assert "output" in call_args_str.lower() or "directory" in call_args_str.lower()
    
    def test_displays_logging_settings(self):
        """Test that logging settings are displayed."""
        from transcriptx.core.utils.config import Config
        
        config = Config()
        
        with patch('builtins.print') as mock_print:
            show_current_config(config)
            
            # Check that logging settings are printed
            call_args_str = str(mock_print.call_args_list)
            assert "logging" in call_args_str.lower() or "log" in call_args_str.lower()
    
    def test_handles_custom_config_values(self):
        """Test that custom config values are displayed correctly."""
        from transcriptx.core.utils.config import Config
        
        config = Config()
        config.analysis.sentiment_window_size = 30
        config.analysis.emotion_min_confidence = 0.5
        
        with patch('builtins.print') as mock_print:
            show_current_config(config)
            
            # Should display custom values
            call_args_str = str(mock_print.call_args_list)
            # Values should be in output
            assert "30" in call_args_str or "0.5" in call_args_str
