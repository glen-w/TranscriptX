"""Unit tests for LLMSettingsModel validators and applied-settings validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from transcriptx.core.config.models.llm import (
    LLMSettingsModel,
    _first_pydantic_message,
    llm_settings_payload_from_applied,
    validate_llm_settings_applied,
)
from transcriptx.core.utils.config.config_errors import ConfigLoadError


@pytest.mark.unit
def test_max_output_tokens_rejects_zero() -> None:
    with pytest.raises(ValidationError, match="max_output_tokens must be >= 1"):
        LLMSettingsModel(max_output_tokens=0)


@pytest.mark.unit
def test_max_output_tokens_allows_none() -> None:
    model = LLMSettingsModel(max_output_tokens=None)
    assert model.max_output_tokens is None


@pytest.mark.unit
def test_first_pydantic_message_defaults_on_empty_errors() -> None:
    class _FakeExc:
        def errors(self):
            return []

    assert _first_pydantic_message(_FakeExc()) == "Invalid LLM configuration."


@pytest.mark.unit
def test_payload_from_applied_merges_dict_over_defaults() -> None:
    payload = llm_settings_payload_from_applied({"enabled": True, "model": "m"})
    assert payload["enabled"] is True
    assert payload["model"] == "m"
    assert payload["provider"] == "null"


@pytest.mark.unit
def test_validate_llm_settings_applied_raises_config_load_error() -> None:
    with pytest.raises(ConfigLoadError):
        validate_llm_settings_applied({"max_output_tokens": 0})


@pytest.mark.unit
def test_validate_llm_settings_applied_accepts_defaults() -> None:
    validate_llm_settings_applied({})
