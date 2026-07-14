"""Tests for system env overrides."""

from __future__ import annotations

import pytest

from transcriptx.core.utils.config.config_errors import ConfigLoadError
from transcriptx.core.utils.config.main import TranscriptXConfig
from transcriptx.core.utils.config.system_env import apply_env_overrides
from transcriptx.core.utils.config.workflow import SpeakerGateConfig


@pytest.mark.unit
def test_apply_env_overrides_rejects_legacy_audio_enabled_env(monkeypatch) -> None:
    cfg = TranscriptXConfig()
    monkeypatch.setenv("TRANSCRIPTX_AUDIO_NORMALIZE_ENABLED", "1")
    with pytest.raises(ConfigLoadError):
        apply_env_overrides(cfg)


@pytest.mark.unit
def test_apply_env_overrides_updates_semantic_model(monkeypatch) -> None:
    cfg = TranscriptXConfig()
    monkeypatch.setenv("TRANSCRIPTX_SEMANTIC_MODEL", "sentence-transformers/test-model")
    apply_env_overrides(cfg)
    assert cfg.analysis.semantic_model_name == "sentence-transformers/test-model"


@pytest.mark.unit
def test_apply_env_overrides_parses_wav_folders_csv_fallback(monkeypatch) -> None:
    cfg = TranscriptXConfig()
    monkeypatch.setenv("TRANSCRIPTX_WAV_FOLDERS", " /tmp/a , /tmp/b ,, ")
    apply_env_overrides(cfg)
    assert cfg.input.wav_folders == ["/tmp/a", "/tmp/b"]


@pytest.mark.unit
def test_apply_env_overrides_accepts_recordings_folders_json(monkeypatch) -> None:
    cfg = TranscriptXConfig()
    monkeypatch.setenv("TRANSCRIPTX_RECORDINGS_FOLDERS", '["/r1","/r2"]')
    apply_env_overrides(cfg)
    assert cfg.input.recordings_folders == ["/r1", "/r2"]


@pytest.mark.unit
def test_apply_env_overrides_audio_convert_to_mono_boolean_mapping(monkeypatch) -> None:
    cfg = TranscriptXConfig()
    monkeypatch.setenv("TRANSCRIPTX_AUDIO_CONVERT_TO_MONO", "true")
    apply_env_overrides(cfg)
    assert cfg.audio_preprocessing.convert_to_mono == "auto"


@pytest.mark.unit
def test_apply_env_overrides_use_emojis_false_mapping(monkeypatch) -> None:
    cfg = TranscriptXConfig()
    monkeypatch.setenv("TRANSCRIPTX_USE_EMOJIS", "off")
    apply_env_overrides(cfg)
    assert cfg.use_emojis is False


@pytest.mark.unit
def test_apply_env_overrides_downsample_false_mapping(monkeypatch) -> None:
    cfg = TranscriptXConfig()
    monkeypatch.setenv("TRANSCRIPTX_AUDIO_DOWNSAMPLE", "0")
    apply_env_overrides(cfg)
    assert cfg.audio_preprocessing.downsample == "off"


@pytest.mark.unit
def test_apply_env_overrides_wav_folders_json_list_preferred(monkeypatch) -> None:
    cfg = TranscriptXConfig()
    monkeypatch.setenv("TRANSCRIPTX_WAV_FOLDERS", '["/x","/y"]')
    apply_env_overrides(cfg)
    assert cfg.input.wav_folders == ["/x", "/y"]


@pytest.mark.unit
def test_apply_env_overrides_honors_file_selection_mode(monkeypatch) -> None:
    cfg = TranscriptXConfig()
    monkeypatch.setenv("TRANSCRIPTX_FILE_SELECTION_MODE", "explore")
    apply_env_overrides(cfg)
    assert cfg.input.file_selection_mode == "explore"


@pytest.mark.unit
def test_apply_env_overrides_honors_speaker_gate_mode(monkeypatch) -> None:
    cfg = TranscriptXConfig()
    cfg.workflow.speaker_gate = SpeakerGateConfig()
    monkeypatch.setenv("TRANSCRIPTX_SPEAKER_GATE_MODE", "enforce")
    apply_env_overrides(cfg)
    assert cfg.workflow.speaker_gate.mode == "enforce"
