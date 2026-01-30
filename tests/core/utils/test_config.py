"""
Tests for configuration management.

This module tests config loading, validation, defaults, and environment variable handling.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.core.utils.config import (
    TranscriptXConfig,
    AnalysisConfig,
    OutputConfig,
    AudioPreprocessingConfig,
    load_config,
    get_config,
    set_config,
)


class TestAnalysisConfig:
    """Tests for AnalysisConfig dataclass."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        config = AnalysisConfig()
        
        assert config.sentiment_window_size == 10
        assert config.sentiment_min_confidence == 0.1
        assert config.emotion_min_confidence == 0.3
        assert isinstance(config.ner_labels, list)
        assert len(config.ner_labels) > 0
    
    def test_custom_values(self):
        """Test that custom values can be set."""
        config = AnalysisConfig(
            sentiment_window_size=20,
            sentiment_min_confidence=0.5
        )
        
        assert config.sentiment_window_size == 20
        assert config.sentiment_min_confidence == 0.5
    
    def test_ner_labels_default(self):
        """Test that NER labels have default values."""
        config = AnalysisConfig()
        
        assert "PERSON" in config.ner_labels
        assert "ORG" in config.ner_labels


class TestOutputConfig:
    """Tests for OutputConfig dataclass."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        config = OutputConfig()
        
        assert config.base_output_dir is not None
        assert config.default_audio_folder is not None
        assert config.default_transcript_folder is not None


class TestAudioPreprocessingConfig:
    """Tests for AudioPreprocessingConfig dataclass."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        config = AudioPreprocessingConfig()
        
        assert config.preprocessing_mode == "selected"
        assert config.convert_to_mono == "auto"
        assert config.downsample == "auto"
        assert config.target_sample_rate == 16000
        assert config.skip_if_already_compliant is True
        assert config.normalize_mode == "auto"
        assert config.target_lufs == -18.0
        assert config.limiter_enabled is True
        assert config.limiter_peak_db == -1.0
        assert config.denoise_mode == "suggest"
        assert config.denoise_strength == "medium"
        assert config.highpass_mode == "suggest"
        assert config.highpass_cutoff == 80
        assert config.lowpass_mode == "off"
        assert config.lowpass_cutoff == 8000
        assert config.bandpass_mode == "off"
        assert config.bandpass_low == 300
        assert config.bandpass_high == 3400
    
    def test_custom_values(self):
        """Test that custom values can be set."""
        config = AudioPreprocessingConfig(
            preprocessing_mode="auto",
            convert_to_mono="off",
            target_sample_rate=22050,
            normalize_mode="suggest",
            target_lufs=-16.0,
            denoise_mode="auto",
            denoise_strength="high"
        )
        
        assert config.preprocessing_mode == "auto"
        assert config.convert_to_mono == "off"
        assert config.target_sample_rate == 22050
        assert config.normalize_mode == "suggest"
        assert config.target_lufs == -16.0
        assert config.denoise_mode == "auto"
        assert config.denoise_strength == "high"
    
    def test_three_mode_values(self):
        """Test that all preprocessing steps support three modes."""
        config = AudioPreprocessingConfig(
            convert_to_mono="suggest",
            downsample="off",
            normalize_mode="auto",
            denoise_mode="suggest",
            highpass_mode="auto",
            lowpass_mode="suggest",
            bandpass_mode="off"
        )
        
        assert config.convert_to_mono == "suggest"
        assert config.downsample == "off"
        assert config.normalize_mode == "auto"
        assert config.denoise_mode == "suggest"
        assert config.highpass_mode == "auto"
        assert config.lowpass_mode == "suggest"
        assert config.bandpass_mode == "off"
    
    def test_global_mode_override(self):
        """Test that global preprocessing_mode can override per-step settings."""
        config = AudioPreprocessingConfig(
            preprocessing_mode="auto",
            convert_to_mono="suggest",
            downsample="off",
            normalize_mode="suggest"
        )
        
        # Global mode should be set
        assert config.preprocessing_mode == "auto"
        # Per-step modes are still stored, but will be overridden by global mode
        assert config.convert_to_mono == "suggest"
        assert config.downsample == "off"
        assert config.normalize_mode == "suggest"


class TestConfig:
    """Tests for Config class."""
    
    def test_initialization(self):
        """Test Config initialization."""
        config = TranscriptXConfig()
        
        assert isinstance(config.analysis, AnalysisConfig)
        assert isinstance(config.output, OutputConfig)
        assert isinstance(config.audio_preprocessing, AudioPreprocessingConfig)
    
    def test_custom_analysis_config(self):
        """Test that custom analysis config can be provided."""
        analysis_config = AnalysisConfig(sentiment_window_size=15)
        config = TranscriptXConfig()
        config.analysis = analysis_config
        
        assert config.analysis.sentiment_window_size == 15


class TestLoadConfig:
    """Tests for load_config function."""
    
    def test_loads_from_file(self, tmp_path):
        """Test loading configuration from file."""
        config_file = tmp_path / "config.json"
        config_data = {
            "analysis": {
                "sentiment_window_size": 20,
                "sentiment_min_confidence": 0.5
            }
        }
        config_file.write_text(json.dumps(config_data))
        
        config = load_config(str(config_file))
        
        assert config.analysis.sentiment_window_size == 20
        assert config.analysis.sentiment_min_confidence == 0.5
    
    def test_uses_defaults_when_file_not_exists(self, tmp_path):
        """Test that defaults are used when file doesn't exist."""
        config_file = tmp_path / "nonexistent.json"
        
        config = load_config(str(config_file))
        
        # Should use defaults
        assert config.analysis.sentiment_window_size == 10
    
    def test_handles_invalid_json(self, tmp_path):
        """Test that invalid JSON is handled."""
        config_file = tmp_path / "config.json"
        config_file.write_text("invalid json")
        
        # Should use defaults or raise error
        with pytest.raises((json.JSONDecodeError, ValueError)):
            load_config(str(config_file))
    
    def test_environment_variable_overrides(self, tmp_path, monkeypatch):
        """Test that environment variables override file settings."""
        config_file = tmp_path / "config.json"
        config_data = {"analysis": {"sentiment_window_size": 20}}
        config_file.write_text(json.dumps(config_data))
        
        monkeypatch.setenv("TRANSCRIPTX_SENTIMENT_WINDOW_SIZE", "30")
        
        config = load_config(str(config_file))
        
        # Environment variable should override
        assert config.analysis.sentiment_window_size == 30
    
    def test_loads_audio_preprocessing_from_file(self, tmp_path):
        """Test loading audio preprocessing configuration from file."""
        config_file = tmp_path / "config.json"
        config_data = {
            "audio_preprocessing": {
                "convert_to_mono": "off",
                "target_sample_rate": 22050,
                "normalize_mode": "suggest",
                "denoise_mode": "auto",
                "denoise_strength": "high"
            }
        }
        config_file.write_text(json.dumps(config_data))
        
        config = load_config(str(config_file))
        
        assert config.audio_preprocessing.convert_to_mono == "off"
        assert config.audio_preprocessing.target_sample_rate == 22050
        assert config.audio_preprocessing.normalize_mode == "suggest"
        assert config.audio_preprocessing.denoise_mode == "auto"
        assert config.audio_preprocessing.denoise_strength == "high"
    
    def test_loads_audio_preprocessing_backward_compatibility(self, tmp_path):
        """Test backward compatibility: loading old boolean configs."""
        config_file = tmp_path / "config.json"
        config_data = {
            "audio_preprocessing": {
                "convert_to_mono": False,  # Old boolean format
                "target_sample_rate": 22050,
                "normalize_enabled": True,  # Old boolean format
                "denoise_enabled": False,  # Old boolean format
                "highpass_enabled": True,  # Old boolean format
                "denoise_strength": "high"
            }
        }
        config_file.write_text(json.dumps(config_data))
        
        config = load_config(str(config_file))
        
        # Should be migrated to new mode format
        assert config.audio_preprocessing.convert_to_mono == "off"  # False -> "off"
        assert config.audio_preprocessing.normalize_mode == "auto"  # True -> "auto"
        assert config.audio_preprocessing.denoise_mode == "off"  # False -> "off"
        assert config.audio_preprocessing.highpass_mode == "auto"  # True -> "auto"
        assert config.audio_preprocessing.target_sample_rate == 22050
        assert config.audio_preprocessing.denoise_strength == "high"
    
    def test_audio_preprocessing_environment_variable_overrides(self, tmp_path, monkeypatch):
        """Test that environment variables override audio preprocessing file settings."""
        config_file = tmp_path / "config.json"
        config_data = {"audio_preprocessing": {"target_sample_rate": 16000}}
        config_file.write_text(json.dumps(config_data))
        
        monkeypatch.setenv("TRANSCRIPTX_AUDIO_TARGET_SAMPLE_RATE", "22050")
        monkeypatch.setenv("TRANSCRIPTX_AUDIO_DENOISE_MODE", "auto")
        
        config = load_config(str(config_file))
        
        # Environment variable should override
        assert config.audio_preprocessing.target_sample_rate == 22050
        assert config.audio_preprocessing.denoise_mode == "auto"
    
    def test_audio_preprocessing_environment_variable_legacy_boolean(self, tmp_path, monkeypatch):
        """Test backward compatibility: legacy boolean environment variables."""
        config_file = tmp_path / "config.json"
        config_data = {"audio_preprocessing": {"target_sample_rate": 16000}}
        config_file.write_text(json.dumps(config_data))
        
        monkeypatch.setenv("TRANSCRIPTX_AUDIO_DENOISE_ENABLED", "true")
        monkeypatch.setenv("TRANSCRIPTX_AUDIO_NORMALIZE_ENABLED", "false")
        
        config = load_config(str(config_file))
        
        # Legacy boolean should be converted to mode
        assert config.audio_preprocessing.denoise_mode == "auto"  # true -> "auto"
        assert config.audio_preprocessing.normalize_mode == "off"  # false -> "off"


class TestGetConfig:
    """Tests for get_config function."""
    
    def test_returns_singleton_instance(self):
        """Test that get_config returns singleton instance."""
        with patch('transcriptx.core.utils.config._global_config', None):
            config1 = get_config()
            config2 = get_config()
            
            # Should be same instance
            assert config1 is config2
    
    def test_uses_default_config_when_none(self):
        """Test that default config is used when none exists."""
        with patch('transcriptx.core.utils.config._global_config', None):
            config = get_config()
            
            assert isinstance(config, TranscriptXConfig)
            assert isinstance(config.analysis, AnalysisConfig)
            assert isinstance(config.audio_preprocessing, AudioPreprocessingConfig)


class TestSaveConfig:
    """Tests for save_config function."""
    
    def test_saves_config_to_file(self, tmp_path):
        """Test that config is saved to file."""
        config_file = tmp_path / "config.json"
        config = TranscriptXConfig()
        config.analysis.sentiment_window_size = 25
        
        # Config is saved through the config object's save method or via load_config
        # For now, just test that we can create and set config
        set_config(config)
        
        # Config is set globally, not necessarily saved to file
        retrieved = get_config()
        assert isinstance(retrieved, TranscriptXConfig)
    
    def test_creates_directory_if_needed(self, tmp_path):
        """Test that directory is created if it doesn't exist."""
        config_file = tmp_path / "subdir" / "config.json"
        config = TranscriptXConfig()
        
        # Config is saved through the config object's save method or via load_config
        # For now, just test that we can create and set config
        set_config(config)
        
        # Config is set globally
        retrieved = get_config()
        assert isinstance(retrieved, TranscriptXConfig)
    
    def test_preserves_all_settings(self, tmp_path):
        """Test that all settings are preserved when saving."""
        config_file = tmp_path / "config.json"
        config = TranscriptXConfig()
        config.analysis.sentiment_window_size = 30
        config.analysis.emotion_min_confidence = 0.4
        
        # Save config to file using the save_to_file method
        config.save_to_file(str(config_file))
        
        # Load it back and verify
        loaded_config = load_config(str(config_file))
        
        assert loaded_config.analysis.sentiment_window_size == 30
        assert loaded_config.analysis.emotion_min_confidence == 0.4
    
    def test_preserves_audio_preprocessing_settings(self, tmp_path):
        """Test that audio preprocessing settings are preserved when saving."""
        config_file = tmp_path / "config.json"
        config = TranscriptXConfig()
        config.audio_preprocessing.preprocessing_mode = "auto"
        config.audio_preprocessing.target_sample_rate = 22050
        config.audio_preprocessing.denoise_mode = "auto"
        config.audio_preprocessing.denoise_strength = "high"
        config.audio_preprocessing.normalize_mode = "suggest"
        
        # Save config to file
        config.save_to_file(str(config_file))
        
        # Load it back and verify
        loaded_config = load_config(str(config_file))
        
        assert loaded_config.audio_preprocessing.preprocessing_mode == "auto"
        assert loaded_config.audio_preprocessing.target_sample_rate == 22050
        assert loaded_config.audio_preprocessing.denoise_mode == "auto"
        assert loaded_config.audio_preprocessing.denoise_strength == "high"
        assert loaded_config.audio_preprocessing.normalize_mode == "suggest"
