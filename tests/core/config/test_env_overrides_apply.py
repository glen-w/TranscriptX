"""TRANSCRIPTX_* env application onto config."""

from __future__ import annotations

import pytest

from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.config_errors import ConfigLoadError
from transcriptx.core.utils.config.env_key_registry import (
    _reject_legacy_audio_enabled_env,
)
from transcriptx.core.utils.config.env_overrides import apply_transcriptx_env


@pytest.fixture(autouse=True)
def _clear_legacy_audio_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "TRANSCRIPTX_AUDIO_NORMALIZE_ENABLED",
        "TRANSCRIPTX_AUDIO_DENOISE_ENABLED",
        "TRANSCRIPTX_AUDIO_HIGHPASS_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.unit
def test_reject_legacy_audio_enabled_env_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRANSCRIPTX_AUDIO_NORMALIZE_ENABLED", "1")
    with pytest.raises(ConfigLoadError, match="no longer supported"):
        _reject_legacy_audio_enabled_env()
    monkeypatch.delenv("TRANSCRIPTX_AUDIO_NORMALIZE_ENABLED", raising=False)


@pytest.mark.unit
def test_apply_transcriptx_core_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_CORE", "true")
    cfg = TranscriptXConfig()
    apply_transcriptx_env(cfg)
    assert cfg.core_mode is True
    monkeypatch.delenv("TRANSCRIPTX_CORE", raising=False)


@pytest.mark.unit
def test_apply_transcriptx_output_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_OUTPUT_DIR", "/tmp/out_xyz")
    cfg = TranscriptXConfig()
    apply_transcriptx_env(cfg)
    assert cfg.output.base_output_dir == "/tmp/out_xyz"
    monkeypatch.delenv("TRANSCRIPTX_OUTPUT_DIR", raising=False)


@pytest.mark.unit
def test_apply_transcriptx_sentiment_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_SENTIMENT_WINDOW_SIZE", "42")
    cfg = TranscriptXConfig()
    apply_transcriptx_env(cfg)
    assert cfg.analysis.sentiment_window_size == 42
    monkeypatch.delenv("TRANSCRIPTX_SENTIMENT_WINDOW_SIZE", raising=False)


@pytest.mark.unit
def test_apply_transcriptx_semantic_progress_log_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRANSCRIPTX_SEMANTIC_PROGRESS_LOG_INTERVAL_SECONDS", "15")
    cfg = TranscriptXConfig()
    apply_transcriptx_env(cfg)
    assert cfg.analysis.semantic_progress_log_interval_seconds == 15.0
    monkeypatch.delenv(
        "TRANSCRIPTX_SEMANTIC_PROGRESS_LOG_INTERVAL_SECONDS", raising=False
    )


@pytest.mark.unit
def test_apply_transcriptx_module_progress_log_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRANSCRIPTX_MODULE_PROGRESS_LOG_INTERVAL_SECONDS", "20")
    cfg = TranscriptXConfig()
    apply_transcriptx_env(cfg)
    assert cfg.analysis.module_progress_log_interval_seconds == 20.0
    monkeypatch.delenv(
        "TRANSCRIPTX_MODULE_PROGRESS_LOG_INTERVAL_SECONDS", raising=False
    )


@pytest.mark.unit
def test_apply_transcriptx_wav_folders_json_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRANSCRIPTX_WAV_FOLDERS", '["/a","/b"]')
    cfg = TranscriptXConfig()
    apply_transcriptx_env(cfg)
    assert cfg.input.wav_folders == ["/a", "/b"]
    monkeypatch.delenv("TRANSCRIPTX_WAV_FOLDERS", raising=False)


@pytest.mark.unit
def test_apply_transcriptx_wav_folders_comma_split(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRANSCRIPTX_WAV_FOLDERS", " /x , /y ")
    cfg = TranscriptXConfig()
    apply_transcriptx_env(cfg)
    assert cfg.input.wav_folders == ["/x", "/y"]
    monkeypatch.delenv("TRANSCRIPTX_WAV_FOLDERS", raising=False)
