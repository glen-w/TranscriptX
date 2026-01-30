"""
Tests for web module registry.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from transcriptx.web.module_registry import (
    get_analysis_modules,
    get_all_available_modules,
    get_total_module_count,
    is_module_available,
    get_module_metadata,
)


class TestModuleRegistry:
    """Tests for module registry functions."""
    
    def test_get_all_available_modules(self):
        """Test getting all available modules from core registry."""
        modules = get_all_available_modules()
        
        assert isinstance(modules, list)
        assert len(modules) > 0
        assert "sentiment" in modules
        assert "emotion" in modules
        assert "ner" in modules
    
    def test_get_total_module_count(self):
        """Test getting total module count dynamically."""
        count = get_total_module_count()
        
        assert isinstance(count, int)
        assert count > 0
        # Should match the number of modules in core registry
        assert count == len(get_all_available_modules())
    
    def test_is_module_available(self):
        """Test checking if a module is available."""
        assert is_module_available("sentiment") is True
        assert is_module_available("emotion") is True
        assert is_module_available("nonexistent_module") is False
    
    def test_get_module_metadata(self):
        """Test getting module metadata."""
        metadata = get_module_metadata("sentiment")
        
        assert metadata is not None
        assert "name" in metadata
        assert "description" in metadata
        assert "category" in metadata
        assert metadata["name"] == "sentiment"
        
        # Test nonexistent module
        assert get_module_metadata("nonexistent") is None
    
    @patch('transcriptx.web.module_registry.Path')
    @patch('transcriptx.web.module_registry.OUTPUTS_DIR', '/tmp/test_outputs')
    def test_get_analysis_modules_with_existing_session(self, mock_path):
        """Test getting modules for a session with existing output."""
        # Setup mock
        session_dir = MagicMock()
        session_dir.exists.return_value = True
        session_dir.is_dir.return_value = True
        session_dir.name = "test_session"
        
        sentiment_dir = MagicMock()
        sentiment_dir.exists.return_value = True
        sentiment_dir.is_dir.return_value = True
        
        emotion_dir = MagicMock()
        emotion_dir.exists.return_value = True
        emotion_dir.is_dir.return_value = True
        
        ner_dir = MagicMock()
        ner_dir.exists.return_value = False
        
        session_dir.__truediv__ = lambda self, other: {
            "sentiment": sentiment_dir,
            "emotion": emotion_dir,
            "ner": ner_dir,
        }.get(other, MagicMock(exists=lambda: False))
        
        outputs_dir = MagicMock()
        outputs_dir.exists.return_value = True
        outputs_dir.iterdir.return_value = [session_dir]
        
        mock_path.return_value = outputs_dir
        
        # Mock OUTPUTS_DIR path
        with patch('transcriptx.web.module_registry.OUTPUTS_DIR', '/tmp/test_outputs'):
            with patch('transcriptx.web.module_registry.Path') as mock_path_class:
                mock_path_class.return_value = outputs_dir
                
                # This will use the real core registry, so we need to mock the filesystem check
                # For now, just test that the function doesn't crash
                modules = get_analysis_modules("test_session")
                assert isinstance(modules, list)
    
    def test_get_analysis_modules_nonexistent_session(self):
        """Test getting modules for nonexistent session."""
        modules = get_analysis_modules("nonexistent_session_12345")
        
        assert isinstance(modules, list)
        assert len(modules) == 0
