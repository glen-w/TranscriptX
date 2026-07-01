"""Pydantic schema for audio preprocessing settings."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

PreprocessingMode = Literal["auto", "suggest", "off"]
GlobalPreprocessingMode = Literal["selected", "auto", "suggest", "off"]
DenoiseStrength = Literal["low", "medium", "high"]


def audio_preprocessing_payload_from_applied(audio: Any) -> dict[str, Any]:
    """Merge applied audio_preprocessing config with model defaults."""
    defaults = AudioPreprocessingSettingsModel().model_dump()
    if isinstance(audio, dict):
        return {**defaults, **audio}
    return {
        **defaults,
        **{
            name: getattr(audio, name)
            for name in AudioPreprocessingSettingsModel.model_fields
        },
    }


def validate_audio_preprocessing_applied(audio: Any) -> None:
    """Validate applied audio preprocessing settings (shared with validate_config)."""
    from pydantic import ValidationError as PydanticValidationError

    payload = audio_preprocessing_payload_from_applied(audio)
    try:
        AudioPreprocessingSettingsModel.model_validate(payload)
    except PydanticValidationError as exc:
        message = _first_pydantic_message(exc)
        raise ValueError(message) from exc


def _first_pydantic_message(exc: Any) -> str:
    errors = exc.errors()
    if not errors:
        return "Invalid audio preprocessing configuration."
    return str(errors[0].get("msg", "Invalid audio preprocessing configuration."))


class AudioPreprocessingSettingsModel(BaseModel):
    """Canonical field definitions for audio preprocessing configuration."""

    preprocessing_mode: GlobalPreprocessingMode = Field(default="selected")
    convert_to_mono: PreprocessingMode = Field(default="auto")
    downsample: PreprocessingMode = Field(default="auto")
    target_sample_rate: int = Field(default=16000)
    skip_if_already_compliant: bool = Field(default=True)
    normalize_mode: PreprocessingMode = Field(default="auto")
    target_lufs: float = Field(default=-18.0, ge=-20.0, le=-16.0)
    limiter_enabled: bool = Field(default=True)
    limiter_peak_db: float = Field(default=-1.0)
    denoise_mode: PreprocessingMode = Field(default="suggest")
    denoise_strength: DenoiseStrength = Field(default="medium")
    highpass_mode: PreprocessingMode = Field(default="suggest")
    highpass_cutoff: int = Field(default=80, ge=70, le=100)
    lowpass_mode: PreprocessingMode = Field(default="off")
    lowpass_cutoff: int = Field(default=8000)
    bandpass_mode: PreprocessingMode = Field(default="off")
    bandpass_low: int = Field(default=300)
    bandpass_high: int = Field(default=3400)
