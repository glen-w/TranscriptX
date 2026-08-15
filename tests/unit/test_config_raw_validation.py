"""Unit tests for raw JSON config validation and wrapper unwrap."""

from __future__ import annotations

import pytest

from transcriptx.core.utils.config.config_errors import ConfigLoadError
from transcriptx.core.utils.config.config_raw_validation import (
    unwrap_config_payload,
    validate_raw_config_dict,
)


@pytest.mark.unit
def test_unwrap_rejects_non_object() -> None:
    with pytest.raises(ConfigLoadError, match="JSON object") as exc:
        unwrap_config_payload([1, 2])
    assert exc.value.code == "invalid_value"


@pytest.mark.unit
def test_unwrap_returns_flat_dict_unchanged() -> None:
    payload = {"analysis": {}, "output": {}}
    assert unwrap_config_payload(payload) is payload


@pytest.mark.unit
def test_unwrap_project_wrapper_returns_inner_config() -> None:
    inner = {"analysis": {"sentiment_window_size": 3}}
    raw = {"schema_version": 1, "config": inner, "extra": "ignored"}
    assert unwrap_config_payload(raw) is inner


@pytest.mark.unit
def test_validate_rejects_transcription_section() -> None:
    with pytest.raises(ConfigLoadError, match="analysis-only") as exc:
        validate_raw_config_dict({"transcription": {}})
    assert exc.value.code == "unknown_section"


@pytest.mark.unit
def test_validate_rejects_unknown_top_level_key() -> None:
    with pytest.raises(ConfigLoadError, match="Unknown configuration section") as exc:
        validate_raw_config_dict({"not_a_section": {}})
    assert exc.value.code == "unknown_section"


@pytest.mark.unit
def test_validate_rejects_legacy_overview_chart_types() -> None:
    with pytest.raises(ConfigLoadError, match="overview_charts") as exc:
        validate_raw_config_dict({"dashboard": {"overview_chart_types": ["sentiment"]}})
    assert exc.value.code == "unsupported_legacy_shape"


@pytest.mark.unit
def test_validate_rejects_unknown_llm_key() -> None:
    with pytest.raises(ConfigLoadError, match="Unknown llm configuration key") as exc:
        validate_raw_config_dict({"llm": {"enabled": True, "mystery": 1}})
    assert exc.value.code == "unknown_section"


@pytest.mark.unit
def test_validate_rejects_legacy_audio_bool_key() -> None:
    with pytest.raises(ConfigLoadError, match="normalize_mode") as exc:
        validate_raw_config_dict({"audio_preprocessing": {"normalize_enabled": True}})
    assert exc.value.code == "unsupported_legacy_shape"


@pytest.mark.unit
def test_validate_accepts_minimal_known_sections() -> None:
    validate_raw_config_dict(
        {
            "analysis": {},
            "output": {},
            "logging": {},
            "llm": {"enabled": False},
        }
    )
