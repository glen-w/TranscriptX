"""Validation consolidation tests for speaker_gate and audio_preprocessing."""

from __future__ import annotations

import pytest

from transcriptx.core.config import get_default_config_dict, validate_config
from transcriptx.core.utils.config.config_errors import ConfigLoadError
from transcriptx.core.utils.config.config_raw_validation import validate_raw_config_dict


@pytest.mark.parametrize(
    "threshold_value",
    [101.0, 150.0],
)
def test_speaker_gate_percentage_above_100_fails_validate_config(
    threshold_value: float,
) -> None:
    errors = validate_config(
        {
            "workflow": {
                "speaker_gate": {
                    "threshold_type": "percentage",
                    "threshold_value": threshold_value,
                }
            }
        }
    )
    assert "workflow.speaker_gate.threshold_value" in errors


def test_speaker_gate_percentage_error_exposed_on_gate_or_threshold() -> None:
    errors = validate_config(
        {
            "workflow": {
                "speaker_gate": {
                    "threshold_type": "percentage",
                    "threshold_value": 101.0,
                }
            }
        }
    )
    assert errors
    assert (
        "workflow.speaker_gate.threshold_value" in errors
        or "workflow.speaker_gate" in errors
    )


def test_speaker_gate_percentage_at_100_passes_validate_config() -> None:
    errors = validate_config(
        {
            "workflow": {
                "speaker_gate": {
                    "threshold_type": "percentage",
                    "threshold_value": 100.0,
                }
            }
        }
    )
    assert "workflow.speaker_gate.threshold_value" not in errors


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("normalize_mode", "invalid-mode"),
        ("denoise_mode", "maybe"),
        ("preprocessing_mode", "always"),
    ],
)
def test_audio_preprocessing_invalid_mode_fails_validate_config(
    field: str, value: str
) -> None:
    errors = validate_config({"audio_preprocessing": {field: value}})
    assert f"audio_preprocessing.{field}" in errors


def test_audio_preprocessing_valid_modes_pass_validate_config() -> None:
    config = get_default_config_dict()
    errors = validate_config(config)
    assert not any(key.startswith("audio_preprocessing.") for key in errors)


def test_raw_config_rejects_boolean_audio_mode_strings() -> None:
    with pytest.raises(ConfigLoadError, match="Boolean value for audio_preprocessing"):
        validate_raw_config_dict({"audio_preprocessing": {"normalize_mode": True}})


def test_raw_config_rejects_invalid_audio_mode_strings() -> None:
    with pytest.raises(ConfigLoadError):
        validate_raw_config_dict(
            {"audio_preprocessing": {"denoise_mode": "invalid-mode"}}
        )
