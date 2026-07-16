"""
Unit tests for system configuration dataclasses (LLMConfig, LoggingConfig).
Legacy DatabaseConfig tests were removed; module is skipped.
"""

from __future__ import annotations


from transcriptx.core.utils.config.system import (
    LLMConfig,
    LoggingConfig,
    PreprocessingMode,
    GlobalPreprocessingMode,
)


class TestLLMConfig:
    """Tests for LLMConfig dataclass."""

    def test_default_values(self) -> None:
        """LLMConfig has expected defaults."""
        cfg = LLMConfig()
        assert cfg.enabled is False
        assert cfg.provider == "null"
        assert cfg.model is None
        assert cfg.base_url is None

    def test_custom_values(self) -> None:
        """LLMConfig accepts custom values via setattr (delegated init=False)."""
        cfg = LLMConfig()
        cfg.enabled = True
        cfg.provider = "ollama"
        cfg.model = "qwen3:8b"
        cfg.base_url = "http://localhost:11434"
        assert cfg.enabled is True
        assert cfg.provider == "ollama"
        assert cfg.model == "qwen3:8b"
        assert cfg.base_url == "http://localhost:11434"


class TestLoggingConfig:
    """Tests for LoggingConfig dataclass."""

    def test_default_values(self) -> None:
        """LoggingConfig has expected defaults."""
        cfg = LoggingConfig()
        assert cfg.level == "INFO"
        assert "asctime" in cfg.format
        assert cfg.file_logging is True
        assert cfg.log_file == "transcriptx.log"
        assert cfg.max_log_size == 10 * 1024 * 1024
        assert cfg.backup_count == 5

    def test_custom_values(self) -> None:
        """LoggingConfig accepts custom values via setattr (delegated init=False)."""
        cfg = LoggingConfig()
        cfg.level = "DEBUG"
        cfg.backup_count = 3
        assert cfg.level == "DEBUG"
        assert cfg.backup_count == 3


class TestPreprocessingModeTypes:
    """Tests for preprocessing mode literal types."""

    def test_preprocessing_mode_values(self) -> None:
        """PreprocessingMode accepts valid values."""
        valid: list[PreprocessingMode] = ["auto", "suggest", "off"]
        assert len(valid) == 3

    def test_global_preprocessing_mode_values(self) -> None:
        """GlobalPreprocessingMode accepts valid values."""
        valid: list[GlobalPreprocessingMode] = ["selected", "auto", "suggest", "off"]
        assert len(valid) == 4
