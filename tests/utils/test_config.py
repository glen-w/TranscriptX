"""
Tests for configuration management.

This module tests configuration loading, validation, and access.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.utils.config import TranscriptXConfig, get_config, load_config


class TestConfig:
    """Tests for configuration management."""
    
    def test_config_initialization(self):
        """Test TranscriptXConfig initialization."""
        config = get_config()
        
        assert hasattr(config, "output")
        assert hasattr(config, "analysis")
    
    def test_get_config(self, mock_config):
        """Test getting configuration instance."""
        config = get_config()
        
        assert config is not None
        assert isinstance(config, TranscriptXConfig)
    
    def test_load_config_from_file(self, tmp_path):
        """Test loading configuration from file."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"output": {"base_output_dir": "/tmp/test"}}')
        
        with patch('transcriptx.core.utils.config.TranscriptXConfig') as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.return_value = mock_config
            
            load_config(str(config_file))
            
            # Should load config
            assert mock_config_class.called
    
    def test_config_output_settings(self, mock_config):
        """Test configuration output settings."""
        config = get_config()
        
        assert hasattr(config.output, "base_output_dir")
        assert isinstance(config.output.base_output_dir, str)
    
    def test_config_analysis_settings(self, mock_config):
        """Test configuration analysis settings."""
        config = get_config()
        
        assert hasattr(config.analysis, "quick_analysis_settings")
        assert hasattr(config.analysis, "full_analysis_settings")
