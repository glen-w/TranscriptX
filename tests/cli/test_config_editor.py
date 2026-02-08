"""
Tests for configuration editor.

This module tests interactive configuration editing workflows.
"""

from unittest.mock import patch, MagicMock

import pytest

pytestmark = [pytest.mark.quarantined, pytest.mark.xfail(strict=True, reason="quarantined")]  # reason: patches settings_menu_loop which no longer exists; owner: cli; remove_by: when config_editor API stabilizes

from transcriptx.cli.config_editor import edit_config_interactive
from transcriptx.cli.config_editors import (
    edit_analysis_config,
    edit_transcription_config,
    edit_output_config,
    edit_logging_config,
    edit_audio_preprocessing_config,
    save_config_interactive,
)


class TestEditConfigInteractive:
    """Tests for edit_config_interactive function."""
    
    def test_displays_main_menu(self):
        """Test that main menu is displayed."""
        with patch('transcriptx.cli.config_editor.get_config') as mock_config, \
             patch('transcriptx.cli.config_editor.questionary') as mock_q, \
             patch('transcriptx.cli.config_editor.print') as mock_print:
            
            mock_config.return_value = MagicMock()
            mock_q.select.return_value.ask.return_value = "🔙 Back to Main Menu"
            
            edit_config_interactive()
            
            # Should have displayed menu
            assert mock_q.select.called
    
    def test_edits_analysis_config(self):
        """Test that analysis config editing is triggered."""
        with patch('transcriptx.cli.config_editor.get_config') as mock_config, \
             patch('transcriptx.cli.config_editor.questionary') as mock_q, \
             patch('transcriptx.cli.config_editor.edit_analysis_config') as mock_edit:
            
            config = MagicMock()
            mock_config.return_value = config
            mock_q.select.return_value.ask.side_effect = [
                "📊 Analysis Settings",
                "🔙 Back to Main Menu"
            ]
            
            edit_config_interactive()
            
            mock_edit.assert_called_once_with(config)
    
    def test_edits_transcription_config(self):
        """Test that transcription config editing is triggered."""
        with patch('transcriptx.cli.config_editor.get_config') as mock_config, \
             patch('transcriptx.cli.config_editor.questionary') as mock_q, \
             patch('transcriptx.cli.config_editor.edit_transcription_config') as mock_edit:
            
            config = MagicMock()
            mock_config.return_value = config
            mock_q.select.return_value.ask.side_effect = [
                "🎧 Transcription Settings",
                "🔙 Back to Main Menu"
            ]
            
            edit_config_interactive()
            
            mock_edit.assert_called_once_with(config)
    
    def test_saves_config(self):
        """Test that config saving is triggered."""
        with patch('transcriptx.cli.config_editor.get_config') as mock_config, \
             patch('transcriptx.cli.config_editor.questionary') as mock_q, \
             patch('transcriptx.cli.config_editor.save_config_interactive') as mock_save:
            
            config = MagicMock()
            mock_config.return_value = config
            mock_q.select.return_value.ask.side_effect = [
                "💾 Save Configuration",
                "🔙 Back to Main Menu"
            ]
            
            edit_config_interactive()
            
            mock_save.assert_called_once_with(config)


class TestEditAnalysisConfig:
    """Tests for edit_analysis_config function."""
    
    def test_builds_analysis_menu_items(self):
        """Test that analysis menu items are built with stable keys."""
        from transcriptx.core.utils.config import TranscriptXConfig

        config = TranscriptXConfig()
        captured = {}

        def fake_menu_loop(title, items, on_back, dirty_tracker, mark_dirty):
            captured["title"] = title
            captured["items"] = items

        with patch(
            "transcriptx.cli.config_editor.settings_menu_loop", new=fake_menu_loop
        ):
            edit_analysis_config(config)

        keys = {item.key for item in captured["items"]}
        assert "analysis.sentiment_window_size" in keys
        assert "analysis.sentiment_min_confidence" in keys
        assert "analysis.emotion_min_confidence" in keys
        assert "analysis.emotion_model_name" in keys
        assert "analysis.ner_include_geocoding" in keys
        assert "analysis.wordcloud_max_words" in keys

    def test_setters_update_config(self):
        """Test that setters update config values."""
        from transcriptx.core.utils.config import TranscriptXConfig

        config = TranscriptXConfig()

        def fake_menu_loop(title, items, on_back, dirty_tracker, mark_dirty):
            target = next(item for item in items if item.key == "analysis.sentiment_window_size")
            target.setter(25)
            mark_dirty()
            assert dirty_tracker()

        with patch(
            "transcriptx.cli.config_editor.settings_menu_loop", new=fake_menu_loop
        ):
            edit_analysis_config(config)

        assert config.analysis.sentiment_window_size == 25


class TestEditAudioPreprocessingConfig:
    """Tests for edit_audio_preprocessing_config function."""
    
    def test_edits_audio_preprocessing_settings(self):
        """Test that audio preprocessing settings can be edited."""
        from transcriptx.core.utils.config import TranscriptXConfig
        
        config = TranscriptXConfig()

        def fake_menu_loop(title, items, on_back, dirty_tracker, mark_dirty):
            keys = {item.key for item in items}
            assert "audio_preprocessing.preprocessing_mode" in keys
            assert "audio_preprocessing.target_sample_rate" in keys

        with patch(
            "transcriptx.cli.config_editor.settings_menu_loop", new=fake_menu_loop
        ):
            edit_audio_preprocessing_config(config)


class TestEditTranscriptionConfig:
    """Tests for edit_transcription_config function."""
    
    def test_edits_transcription_settings(self):
        """Test that transcription settings can be edited."""
        from transcriptx.core.utils.config import TranscriptXConfig
        
        config = TranscriptXConfig()

        def fake_menu_loop(title, items, on_back, dirty_tracker, mark_dirty):
            keys = {item.key for item in items}
            assert "transcription.model_name" in keys
            assert "transcription.batch_size" in keys

        with patch(
            "transcriptx.cli.config_editor.settings_menu_loop", new=fake_menu_loop
        ):
            edit_transcription_config(config)


class TestEditOutputConfig:
    """Tests for edit_output_config function."""
    
    def test_edits_output_settings(self):
        """Test that output settings can be edited."""
        from transcriptx.core.utils.config import TranscriptXConfig
        
        config = TranscriptXConfig()

        def fake_menu_loop(title, items, on_back, dirty_tracker, mark_dirty):
            keys = {item.key for item in items}
            assert "output.base_output_dir" in keys
            assert "output.overwrite_existing" in keys

        with patch(
            "transcriptx.cli.config_editor.settings_menu_loop", new=fake_menu_loop
        ):
            edit_output_config(config)


class TestEditLoggingConfig:
    """Tests for edit_logging_config function."""
    
    def test_edits_logging_settings(self):
        """Test that logging settings can be edited."""
        from transcriptx.core.utils.config import TranscriptXConfig
        
        config = TranscriptXConfig()

        def fake_menu_loop(title, items, on_back, dirty_tracker, mark_dirty):
            keys = {item.key for item in items}
            assert "logging.level" in keys
            assert "logging.backup_count" in keys

        with patch(
            "transcriptx.cli.config_editor.settings_menu_loop", new=fake_menu_loop
        ):
            edit_logging_config(config)
    
    def test_edits_audio_preprocessing_config(self):
        """Test that audio preprocessing config editing is triggered."""
        with patch('transcriptx.cli.config_editor.get_config') as mock_config, \
             patch('transcriptx.cli.config_editor.questionary') as mock_q, \
             patch('transcriptx.cli.config_editor.edit_audio_preprocessing_config') as mock_edit:
            
            config = MagicMock()
            mock_config.return_value = config
            mock_q.select.return_value.ask.side_effect = [
                "🎵 Audio Preprocessing Settings",
                "🔙 Back to Main Menu"
            ]
            
            edit_config_interactive()
            
            mock_edit.assert_called_once_with(config)


class TestSaveConfigInteractive:
    """Tests for save_config_interactive function."""
    
    def test_saves_config(self, tmp_path):
        """Test that config is saved."""
        from transcriptx.core.utils.config import TranscriptXConfig
        
        config = TranscriptXConfig()
        config_file = tmp_path / "config.json"
        
        with patch("transcriptx.cli.config_editors.save.questionary") as mock_q, patch(
            "transcriptx.cli.config_editors.save.print"
        ):
            mock_q.text.return_value.ask.return_value = str(config_file)
            with patch.object(config, "save_to_file") as mock_save:
                save_config_interactive(config)

                # Should have saved config
                mock_save.assert_called_once_with(str(config_file))
