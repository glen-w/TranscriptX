"""Tests for env key registry."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from transcriptx.core.utils.config.config_errors import ConfigLoadError
from transcriptx.core.utils.config.env_key_registry import (
    ENV_KEY_REGISTRY,
    INFRA_ENV_ALLOWLIST,
    KNOWN_OVERRIDE_KEYS,
    LEGACY_REJECTED_KEYS,
    EnvKey,
    _apply_registry_to_config,
    apply_env_to_config,
    coerce_bool_on_off,
    coerce_float,
    coerce_int,
    coerce_json_or_csv_list,
    coerce_lower_strip,
    coerce_str,
    coerce_tri_state_bool_fallback,
)
from transcriptx.core.utils.config.env_overrides import apply_transcriptx_env
from transcriptx.core.utils.config.main import TranscriptXConfig
from transcriptx.core.utils.config.system_env import apply_env_overrides
from transcriptx.core.utils.config.workflow import SpeakerGateConfig


def _build_config_without_env(monkeypatch: pytest.MonkeyPatch) -> TranscriptXConfig:
    with monkeypatch.context() as scoped:
        for key in list(os.environ):
            if key.startswith("TRANSCRIPTX_"):
                scoped.delenv(key, raising=False)
        return TranscriptXConfig()


def _get_path_value(root: object, path: tuple[str, ...]) -> object:
    current = root
    for segment in path:
        current = getattr(current, segment)
    return current


def _entry(env_name: str) -> EnvKey:
    for item in ENV_KEY_REGISTRY:
        if item.env_name == env_name:
            return item
    raise AssertionError(f"Missing registry entry for {env_name}")


def _sample_and_expected(env_name: str) -> tuple[str, object]:
    table = {
        "TRANSCRIPTX_CORE": ("true", True),
        "TRANSCRIPTX_SENTIMENT_WINDOW_SIZE": ("42", 42),
        "TRANSCRIPTX_EMOTION_MODEL": ("emotion/model", "emotion/model"),
        "TRANSCRIPTX_SEMANTIC_MODEL": ("semantic/model", "semantic/model"),
        "TRANSCRIPTX_SEMANTIC_SIMILARITY_MODEL": (
            "semantic/v2-model",
            "semantic/v2-model",
        ),
        "TRANSCRIPTX_SENTIMENT_BACKEND": ("transformers", "transformers"),
        "TRANSCRIPTX_BERTOPIC_EMBEDDING_MODEL": (
            "sentence-transformers/all-mpnet-base-v2",
            "sentence-transformers/all-mpnet-base-v2",
        ),
        "TRANSCRIPTX_BERTOPIC_MIN_TOPIC_SIZE": ("8", 8),
        "TRANSCRIPTX_BERTOPIC_NR_TOPICS": ("12", "12"),
        "TRANSCRIPTX_BERTOPIC_TOP_N_WORDS": ("15", 15),
        "TRANSCRIPTX_BERTOPIC_LABEL_WORDS": ("4", 4),
        "TRANSCRIPTX_BERTOPIC_CALCULATE_PROBABILITIES": ("on", True),
        "TRANSCRIPTX_BERTOPIC_TIMEOUT_SECONDS": ("7200", 7200.0),
        "TRANSCRIPTX_SEMANTIC_PROGRESS_LOG_INTERVAL_SECONDS": ("15.5", 15.5),
        "TRANSCRIPTX_MODULE_PROGRESS_LOG_INTERVAL_SECONDS": ("9", 9.0),
        "TRANSCRIPTX_ACTS_MODEL": ("acts/model", "acts/model"),
        "TRANSCRIPTX_WORDCLOUD_MAX_WORDS": ("123", 123),
        "TRANSCRIPTX_ANALYSIS_ALLOW_UNNAMED_SPEAKERS": ("on", True),
        "TRANSCRIPTX_WAV_FOLDERS": ('["/a","/b"]', ["/a", "/b"]),
        "TRANSCRIPTX_RECORDINGS_FOLDERS": ("/r1,/r2", ["/r1", "/r2"]),
        "TRANSCRIPTX_FILE_SELECTION_MODE": ("explore", "explore"),
        "TRANSCRIPTX_OUTPUT_DIR": ("/tmp/out", "/tmp/out"),
        "TRANSCRIPTX_LOG_LEVEL": ("DEBUG", "DEBUG"),
        "TRANSCRIPTX_USE_EMOJIS": ("off", False),
        "TRANSCRIPTX_METADATA_DURATION_CALCULATION": ("span", "span"),
        "TRANSCRIPTX_METADATA_LISTING_WORD_COUNT_FALLBACK": (
            "metadata_only",
            "metadata_only",
        ),
        "TRANSCRIPTX_METADATA_AUTO_REFRESH_ON_WRITE": ("0", False),
        "TRANSCRIPTX_METADATA_LEGACY_WORDS_ALIAS": ("1", True),
        "TRANSCRIPTX_DASHBOARD_DURATION_HOURS_THRESHOLD": ("7200", 7200),
        "TRANSCRIPTX_DASHBOARD_DURATION_SUMMARY_STYLE": (
            "minutes_only",
            "minutes_only",
        ),
        "TRANSCRIPTX_DASHBOARD_TRANSCRIPT_EXCLUDE_UNNAMED_SPEAKERS": ("0", False),
        "TRANSCRIPTX_AUDIO_PREPROCESSING_MODE": ("auto", "auto"),
        "TRANSCRIPTX_AUDIO_CONVERT_TO_MONO": ("true", "auto"),
        "TRANSCRIPTX_AUDIO_DOWNSAMPLE": ("0", "off"),
        "TRANSCRIPTX_AUDIO_TARGET_SAMPLE_RATE": ("22050", 22050),
        "TRANSCRIPTX_AUDIO_NORMALIZE_MODE": ("suggest", "suggest"),
        "TRANSCRIPTX_AUDIO_TARGET_LUFS": ("-17.5", -17.5),
        "TRANSCRIPTX_AUDIO_DENOISE_MODE": ("off", "off"),
        "TRANSCRIPTX_AUDIO_DENOISE_STRENGTH": ("high", "high"),
        "TRANSCRIPTX_AUDIO_HIGHPASS_MODE": ("auto", "auto"),
        "TRANSCRIPTX_AUDIO_HIGHPASS_CUTOFF": ("120", 120),
        # Speaker gate values are normalized by validate() post-hook.
        "TRANSCRIPTX_SPEAKER_GATE_THRESHOLD_VALUE": ("5.5", 5.5),
        "TRANSCRIPTX_SPEAKER_GATE_THRESHOLD_TYPE": ("percentage", "percentage"),
        "TRANSCRIPTX_SPEAKER_GATE_MODE": ("enforce", "enforce"),
        "TRANSCRIPTX_SPEAKER_GATE_EXEMPLAR_COUNT": ("3", 3),
        "TRANSCRIPTX_LLM_ENABLED": ("1", True),
        "TRANSCRIPTX_LLM_PROVIDER": ("ollama", "ollama"),
        "TRANSCRIPTX_LLM_MODEL": ("qwen3:8b", "qwen3:8b"),
        "TRANSCRIPTX_LLM_BASE_URL": (
            "http://localhost:11434",
            "http://localhost:11434",
        ),
        "TRANSCRIPTX_LLM_SEED": ("7", 7),
        "TRANSCRIPTX_LLM_REQUEST_TIMEOUT": ("90", 90.0),
        "TRANSCRIPTX_LLM_AVAILABILITY_TIMEOUT": ("4", 4.0),
        "TRANSCRIPTX_LLM_MAX_INPUT_CHARS": ("12000", 12000),
        "TRANSCRIPTX_LLM_MAX_OUTPUT_TOKENS": ("1024", 1024),
        "TRANSCRIPTX_LLM_DEFAULT_TEMPERATURE": ("0.25", 0.25),
        "TRANSCRIPTX_CORRECTIONS_LLM_ENABLED": ("1", True),
    }
    return table[env_name]


@pytest.fixture(autouse=True)
def _clear_transcriptx_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("TRANSCRIPTX_"):
            monkeypatch.delenv(key, raising=False)


@pytest.mark.unit
def test_registry_contains_frozen_transcriptx_core_mapping() -> None:
    core_entry = _entry("TRANSCRIPTX_CORE")
    emoji_entry = _entry("TRANSCRIPTX_USE_EMOJIS")
    assert core_entry.target_path == ("core_mode",)
    assert core_entry.coercer is coerce_bool_on_off
    assert emoji_entry.target_path == ("use_emojis",)
    assert emoji_entry.coercer is coerce_bool_on_off


@pytest.mark.unit
def test_registry_completeness_from_env_example() -> None:
    env_example = (Path(__file__).resolve().parents[4] / ".env.example").read_text(
        encoding="utf-8"
    )
    env_keys = {
        line.split("=", 1)[0].strip()
        for line in env_example.splitlines()
        if line.strip().startswith("TRANSCRIPTX_")
    }
    known_union = KNOWN_OVERRIDE_KEYS | INFRA_ENV_ALLOWLIST | set(LEGACY_REJECTED_KEYS)
    missing = sorted(key for key in env_keys if key not in known_union)
    assert missing == []


@pytest.mark.unit
def test_env_example_documents_all_registry_keys() -> None:
    env_example = (Path(__file__).resolve().parents[4] / ".env.example").read_text(
        encoding="utf-8"
    )
    env_keys = {
        line.split("=", 1)[0].strip()
        for line in env_example.splitlines()
        if line.strip().startswith("TRANSCRIPTX_")
    }
    missing = sorted(
        key.env_name for key in ENV_KEY_REGISTRY if key.env_name not in env_keys
    )
    assert missing == []


@pytest.mark.unit
def test_shim_modules_do_not_read_transcriptx_env_directly() -> None:
    root = Path(__file__).resolve().parents[4]
    shim_files = (
        root / "src/transcriptx/core/utils/config/env_overrides.py",
        root / "src/transcriptx/core/utils/config/system_env.py",
    )
    for path in shim_files:
        src = path.read_text(encoding="utf-8")
        assert 'os.getenv("TRANSCRIPTX_' not in src
        assert "os.getenv('TRANSCRIPTX_" not in src


@pytest.mark.unit
@pytest.mark.parametrize("legacy_key", LEGACY_REJECTED_KEYS)
def test_legacy_audio_enabled_keys_raise(
    monkeypatch: pytest.MonkeyPatch, legacy_key: str
) -> None:
    cfg = _build_config_without_env(monkeypatch)
    monkeypatch.setenv(legacy_key, "1")
    with pytest.raises(ConfigLoadError, match="no longer supported"):
        apply_env_to_config(cfg)


@pytest.mark.unit
def test_coercer_behaviors() -> None:
    assert coerce_int("123") == (True, 123)
    assert coerce_int("abc") == (False, None)
    assert coerce_float("1.5") == (True, 1.5)
    assert coerce_float("x") == (False, None)
    assert coerce_str(" value ") == (True, "value")
    assert coerce_str("   ") == (False, None)
    assert coerce_lower_strip(" VaL ") == (True, "val")
    assert coerce_bool_on_off("true") == (True, True)
    assert coerce_bool_on_off("bogus") == (True, False)
    assert coerce_tri_state_bool_fallback("true") == (True, "auto")
    assert coerce_tri_state_bool_fallback("0") == (True, "off")
    assert coerce_tri_state_bool_fallback("invalid") == (False, None)
    assert coerce_json_or_csv_list('["/a"," /b "]') == (True, ["/a", "/b"])
    assert coerce_json_or_csv_list("/a, /b ,") == (True, ["/a", "/b"])
    assert coerce_json_or_csv_list("   ") == (False, None)
    assert coerce_json_or_csv_list(",,") == (False, None)


@pytest.mark.unit
def test_empty_and_whitespace_values_are_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _build_config_without_env(monkeypatch)
    original_out = cfg.output.base_output_dir
    original_wav = list(cfg.input.wav_folders)

    monkeypatch.setenv("TRANSCRIPTX_OUTPUT_DIR", "   ")
    monkeypatch.setenv("TRANSCRIPTX_WAV_FOLDERS", ",,")
    apply_env_to_config(cfg)

    assert cfg.output.base_output_dir == original_out
    assert cfg.input.wav_folders == original_wav


@pytest.mark.unit
@pytest.mark.parametrize("entry", ENV_KEY_REGISTRY, ids=lambda item: item.env_name)
def test_per_key_e2e_application(
    monkeypatch: pytest.MonkeyPatch, entry: EnvKey
) -> None:
    cfg = _build_config_without_env(monkeypatch)
    raw, expected = _sample_and_expected(entry.env_name)
    monkeypatch.setenv(entry.env_name, raw)

    apply_env_to_config(cfg)
    assert _get_path_value(cfg, entry.target_path) == expected


@pytest.mark.unit
def test_speaker_gate_post_hook_runs_once_on_resolved_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _build_config_without_env(monkeypatch)
    cfg.workflow.speaker_gate = SpeakerGateConfig()

    calls = {"count": 0}
    real_validate = SpeakerGateConfig.validate

    def _wrapped(self: SpeakerGateConfig) -> None:
        assert self is cfg.workflow.speaker_gate
        calls["count"] += 1
        real_validate(self)

    monkeypatch.setattr(SpeakerGateConfig, "validate", _wrapped)
    monkeypatch.setenv("TRANSCRIPTX_SPEAKER_GATE_THRESHOLD_VALUE", "-5")
    monkeypatch.setenv("TRANSCRIPTX_SPEAKER_GATE_THRESHOLD_TYPE", "invalid-type")
    monkeypatch.setenv("TRANSCRIPTX_SPEAKER_GATE_MODE", "invalid-mode")
    monkeypatch.setenv("TRANSCRIPTX_SPEAKER_GATE_EXEMPLAR_COUNT", "-3")

    apply_env_to_config(cfg)

    assert calls["count"] == 1
    assert cfg.workflow.speaker_gate.threshold_value == 0.0
    assert cfg.workflow.speaker_gate.threshold_type == "absolute"
    assert cfg.workflow.speaker_gate.mode == "warn"
    assert cfg.workflow.speaker_gate.exemplar_count == 0


@pytest.mark.unit
def test_invalid_policy_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _build_config_without_env(monkeypatch)
    warnings: list[str] = []

    from transcriptx.core.utils.config import env_key_registry as reg

    monkeypatch.setattr(reg, "log_warning", lambda _scope, msg: warnings.append(msg))
    monkeypatch.setenv("TRANSCRIPTX_TEST_SKIP", "bad")
    monkeypatch.setenv("TRANSCRIPTX_TEST_WARN", "bad")
    monkeypatch.setenv("TRANSCRIPTX_TEST_RAISE", "bad")

    def _always_invalid(_raw: str) -> tuple[bool, object | None]:
        return (False, None)

    skip_key = EnvKey(
        env_name="TRANSCRIPTX_TEST_SKIP",
        target_path=("mode",),
        coercer=_always_invalid,
        invalid_policy="skip",
    )
    warn_key = EnvKey(
        env_name="TRANSCRIPTX_TEST_WARN",
        target_path=("mode",),
        coercer=_always_invalid,
        invalid_policy="warn_skip",
    )
    raise_key = EnvKey(
        env_name="TRANSCRIPTX_TEST_RAISE",
        target_path=("mode",),
        coercer=_always_invalid,
        invalid_policy="raise",
    )

    _apply_registry_to_config(cfg, registry=(skip_key, warn_key), strict=False)
    assert any(
        "Skipping TRANSCRIPTX_TEST_WARN" in message and "coercion_failed" in message
        for message in warnings
    )

    with pytest.raises(ConfigLoadError, match="TRANSCRIPTX_TEST_RAISE"):
        _apply_registry_to_config(cfg, registry=(raise_key,), strict=False)


@pytest.mark.unit
def test_unknown_key_warns_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _build_config_without_env(monkeypatch)
    warnings: list[str] = []
    from transcriptx.core.utils.config import env_key_registry as reg

    monkeypatch.setattr(reg, "log_warning", lambda _scope, msg: warnings.append(msg))
    monkeypatch.setenv("TRANSCRIPTX_COMPLETELY_FAKE_KEY", "abc")

    apply_env_to_config(cfg, strict=False)
    assert any("TRANSCRIPTX_COMPLETELY_FAKE_KEY" in item for item in warnings)


@pytest.mark.unit
def test_unknown_key_raises_in_strict_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _build_config_without_env(monkeypatch)
    monkeypatch.setenv("TRANSCRIPTX_CONFIG_STRICT", "1")
    monkeypatch.setenv("TRANSCRIPTX_COMPLETELY_FAKE_KEY", "abc")
    with pytest.raises(ConfigLoadError, match="TRANSCRIPTX_COMPLETELY_FAKE_KEY"):
        apply_env_to_config(cfg)


@pytest.mark.unit
def test_strict_key_self_exclusion(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _build_config_without_env(monkeypatch)
    monkeypatch.setenv("TRANSCRIPTX_CONFIG_STRICT", "1")
    apply_env_to_config(cfg)


@pytest.mark.unit
def test_infra_allowlist_keys_do_not_warn(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _build_config_without_env(monkeypatch)
    warnings: list[str] = []
    from transcriptx.core.utils.config import env_key_registry as reg

    monkeypatch.setattr(reg, "log_warning", lambda _scope, msg: warnings.append(msg))
    monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", "/tmp/data")
    monkeypatch.setenv("TRANSCRIPTX_HOST", "0.0.0.0")

    apply_env_to_config(cfg)
    assert warnings == []


@pytest.mark.unit
@pytest.mark.parametrize("entry", ENV_KEY_REGISTRY, ids=lambda item: item.env_name)
def test_entrypoint_parity_by_touched_path(
    monkeypatch: pytest.MonkeyPatch, entry: EnvKey
) -> None:
    cfg_a = _build_config_without_env(monkeypatch)
    cfg_b = _build_config_without_env(monkeypatch)

    raw, expected = _sample_and_expected(entry.env_name)
    monkeypatch.setenv(entry.env_name, raw)

    apply_transcriptx_env(cfg_a)
    apply_env_overrides(cfg_b)

    assert _get_path_value(cfg_a, entry.target_path) == expected
    assert _get_path_value(cfg_b, entry.target_path) == expected


@pytest.mark.unit
def test_idempotent_application(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _build_config_without_env(monkeypatch)
    cfg.workflow.speaker_gate = SpeakerGateConfig()

    calls = {"count": 0}
    real_validate = SpeakerGateConfig.validate

    def _wrapped(self: SpeakerGateConfig) -> None:
        calls["count"] += 1
        real_validate(self)

    monkeypatch.setattr(SpeakerGateConfig, "validate", _wrapped)
    monkeypatch.setenv("TRANSCRIPTX_SPEAKER_GATE_MODE", "warn")

    apply_env_to_config(cfg)
    apply_env_to_config(cfg)

    assert cfg.workflow.speaker_gate.mode == "warn"
    assert calls["count"] == 2


@pytest.mark.unit
def test_transcriptx_core_semantics_are_frozen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg_true = _build_config_without_env(monkeypatch)
    monkeypatch.setenv("TRANSCRIPTX_CORE", "true")
    apply_env_to_config(cfg_true)
    assert cfg_true.core_mode is True

    monkeypatch.setenv("TRANSCRIPTX_CORE", "bogus")
    cfg_false = _build_config_without_env(monkeypatch)
    apply_env_to_config(cfg_false)
    assert cfg_false.core_mode is False

    monkeypatch.setenv("TRANSCRIPTX_CORE", "")
    cfg_skip = _build_config_without_env(monkeypatch)
    before = cfg_skip.core_mode
    apply_env_to_config(cfg_skip)
    assert cfg_skip.core_mode == before
