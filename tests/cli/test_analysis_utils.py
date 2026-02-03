"""
Tests for analysis utility functions.

This module tests module selection, mode selection, filtering,
and analysis mode settings application.
"""

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.cli.analysis_utils import (
    select_analysis_modules,
    select_analysis_mode,
    apply_analysis_mode_settings,
    filter_modules_by_mode
)


class TestSelectAnalysisModules:
    """Tests for select_analysis_modules function."""
    
    @patch('transcriptx.cli.analysis_utils.questionary.checkbox')
    @patch('transcriptx.cli.analysis_utils.get_available_modules')
    @patch('transcriptx.cli.analysis_utils.get_default_modules')
    def test_select_all_modules(self, mock_get_default, mock_get_modules, mock_checkbox):
        """Test selecting all modules."""
        mock_get_modules.return_value = ["sentiment", "stats", "ner"]
        mock_get_default.return_value = ["sentiment", "stats", "ner"]
        mock_checkbox.return_value.ask.return_value = ["all"]
        
        result = select_analysis_modules()
        
        assert result == ["sentiment", "stats", "ner"]
        mock_checkbox.assert_called_once()
    
    @patch('transcriptx.cli.analysis_utils.questionary.checkbox')
    @patch('transcriptx.cli.analysis_utils.get_available_modules')
    @patch('transcriptx.cli.analysis_utils.get_description')
    def test_select_single_module(self, mock_get_desc, mock_get_modules, mock_checkbox):
        """Test selecting a single module."""
        mock_get_modules.return_value = ["sentiment", "stats"]
        mock_get_desc.return_value = "Sentiment Analysis"
        mock_checkbox.return_value.ask.return_value = ["sentiment"]
        
        result = select_analysis_modules()
        
        assert result == ["sentiment"]
        mock_checkbox.assert_called_once()
    
    @patch('transcriptx.cli.analysis_utils.questionary.checkbox')
    @patch('transcriptx.cli.analysis_utils.get_available_modules')
    def test_select_modules_cancel(self, mock_get_modules, mock_checkbox):
        """Test canceling module selection."""
        mock_get_modules.return_value = ["sentiment"]
        mock_checkbox.return_value.ask.return_value = None
        
        result = select_analysis_modules()
        
        assert result == []
    
    @patch('transcriptx.cli.analysis_utils.questionary.checkbox')
    @patch('transcriptx.cli.analysis_utils.get_available_modules')
    @patch('transcriptx.cli.analysis_utils.edit_config_interactive')
    @patch('transcriptx.cli.analysis_utils.get_default_modules')
    def test_select_modules_invalid_selection(
        self, mock_get_default, mock_edit_config, mock_get_modules, mock_checkbox
    ):
        """Test handling invalid selection."""
        mock_get_modules.return_value = ["sentiment"]
        mock_get_default.return_value = ["sentiment"]
        mock_checkbox.return_value.ask.side_effect = [
            ["settings"],
            ["all"],
        ]
        
        with patch('transcriptx.cli.analysis_utils.print'):
            result = select_analysis_modules()
        
        # Should eventually return valid result
        assert result == ["sentiment"]


class TestSelectAnalysisMode:
    """Tests for select_analysis_mode function."""
    
    @patch('transcriptx.cli.analysis_utils.questionary.select')
    def test_select_quick_mode(self, mock_select):
        """Test selecting quick analysis mode."""
        mock_select.return_value.ask.return_value = "quick"
        
        result = select_analysis_mode()
        
        assert result == "quick"
        mock_select.assert_called_once()
    
    @patch('transcriptx.cli.analysis_utils.questionary.select')
    def test_select_full_mode(self, mock_select):
        """Test selecting full analysis mode."""
        mock_select.return_value.ask.return_value = "full"
        
        result = select_analysis_mode()
        
        assert result == "full"
        mock_select.assert_called_once()


class TestApplyAnalysisModeSettings:
    """Tests for apply_analysis_mode_settings function."""
    
    @patch('transcriptx.cli.analysis_utils.get_config')
    def test_apply_quick_mode_settings(self, mock_get_config):
        """Test applying quick mode settings."""
        mock_config = MagicMock()
        mock_config.analysis.quick_analysis_settings = {
            "semantic_method": "simple",
            "max_segments_for_semantic": 100,
            "max_semantic_comparisons": 1000,
            "ner_use_light_model": True,
            "ner_max_segments": 200,
            "skip_geocoding": True,
            "semantic_profile": "balanced"
        }
        mock_get_config.return_value = mock_config
        
        with patch('transcriptx.cli.analysis_utils.print'):
            apply_analysis_mode_settings("quick")
        
        # Should apply quick settings
        assert mock_config.analysis.analysis_mode == "quick"
        mock_get_config.assert_called_once()
    
    @patch('transcriptx.cli.analysis_utils.get_config')
    @patch('transcriptx.cli.analysis_utils.questionary.select')
    def test_apply_full_mode_settings(self, mock_select, mock_get_config):
        """Test applying full mode settings."""
        mock_config = MagicMock()
        mock_config.analysis.full_analysis_settings = {
            "semantic_method": "advanced",
            "max_segments_for_semantic": 500,
            "max_semantic_comparisons": 5000,
            "ner_use_light_model": False,
            "ner_max_segments": 500,
            "skip_geocoding": False,
            "semantic_profile": "balanced"
        }
        mock_get_config.return_value = mock_config
        mock_select.return_value.ask.return_value = "balanced"
        
        with patch('transcriptx.cli.analysis_utils.print'):
            apply_analysis_mode_settings("full")
        
        # Should apply full settings and prompt for profile
        assert mock_config.analysis.analysis_mode == "full"
        mock_select.assert_called_once()


class TestFilterModulesByMode:
    """Tests for filter_modules_by_mode function."""
    
    @patch('transcriptx.cli.analysis_utils.get_config')
    def test_filter_modules_quick_mode(self, mock_get_config):
        """Test filtering modules in quick mode."""
        mock_config = MagicMock()
        mock_config.analysis.quick_analysis_settings = {
            "skip_advanced_semantic": True
        }
        mock_get_config.return_value = mock_config
        
        modules = ["sentiment", "semantic_similarity_advanced", "stats"]
        result = filter_modules_by_mode(modules, "quick")
        
        # Should filter out semantic_similarity_advanced
        assert "semantic_similarity_advanced" not in result
        assert "sentiment" in result
        assert "stats" in result
    
    @patch('transcriptx.cli.analysis_utils.get_config')
    def test_filter_modules_full_mode(self, mock_get_config):
        """Test filtering modules in full mode."""
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config
        
        modules = ["sentiment", "semantic_similarity_advanced", "stats"]
        result = filter_modules_by_mode(modules, "full")
        
        # Should not filter anything in full mode
        assert result == modules
    
    @patch('transcriptx.cli.analysis_utils.get_config')
    def test_filter_modules_quick_with_replacement(self, mock_get_config):
        """Test filtering with semantic_similarity replacement."""
        mock_config = MagicMock()
        mock_config.analysis.quick_analysis_settings = {
            "skip_advanced_semantic": True
        }
        mock_get_config.return_value = mock_config
        
        modules = ["semantic_similarity_advanced"]  # Only advanced
        result = filter_modules_by_mode(modules, "quick")
        
        # Should replace with semantic_similarity
        assert "semantic_similarity" in result
        assert "semantic_similarity_advanced" not in result
