"""System configuration classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .analysis import _hydrate_dataclass_from_pydantic


@dataclass
class LLMConfig:
    """Defaults owned by LLMSettingsModel."""

    enabled: bool = field(init=False, repr=True)
    provider: str = field(init=False, repr=True)
    model: str | None = field(init=False, repr=True)
    base_url: str | None = field(init=False, repr=True)
    request_timeout: float = field(init=False, repr=True)
    availability_timeout: float = field(init=False, repr=True)
    seed: int = field(init=False, repr=True)
    max_input_chars: int = field(init=False, repr=True)
    max_output_tokens: int | None = field(init=False, repr=True)
    default_temperature: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.llm import (
            LLMSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, LLMSettingsModel())


@dataclass
class LoggingConfig:
    """Defaults owned by LoggingSettingsModel."""

    level: str = field(init=False, repr=True)
    format: str = field(init=False, repr=True)
    file_logging: bool = field(init=False, repr=True)
    log_file: str = field(init=False, repr=True)
    max_log_size: int = field(init=False, repr=True)
    backup_count: int = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.logging import (
            LoggingSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, LoggingSettingsModel())


@dataclass
class AudioPreprocessingConfig:
    """Defaults owned by AudioPreprocessingSettingsModel."""

    preprocessing_mode: Literal["selected", "auto", "suggest", "off"] = field(
        init=False, repr=True
    )
    convert_to_mono: Literal["auto", "suggest", "off"] = field(init=False, repr=True)
    downsample: Literal["auto", "suggest", "off"] = field(init=False, repr=True)
    target_sample_rate: int = field(init=False, repr=True)
    skip_if_already_compliant: bool = field(init=False, repr=True)
    normalize_mode: Literal["auto", "suggest", "off"] = field(init=False, repr=True)
    target_lufs: float = field(init=False, repr=True)
    limiter_enabled: bool = field(init=False, repr=True)
    limiter_peak_db: float = field(init=False, repr=True)
    denoise_mode: Literal["auto", "suggest", "off"] = field(init=False, repr=True)
    denoise_strength: Literal["low", "medium", "high"] = field(init=False, repr=True)
    highpass_mode: Literal["auto", "suggest", "off"] = field(init=False, repr=True)
    highpass_cutoff: int = field(init=False, repr=True)
    lowpass_mode: Literal["auto", "suggest", "off"] = field(init=False, repr=True)
    lowpass_cutoff: int = field(init=False, repr=True)
    bandpass_mode: Literal["auto", "suggest", "off"] = field(init=False, repr=True)
    bandpass_low: int = field(init=False, repr=True)
    bandpass_high: int = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.audio_preprocessing import (
            AudioPreprocessingSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, AudioPreprocessingSettingsModel())


PreprocessingMode = Literal["auto", "suggest", "off"]
GlobalPreprocessingMode = Literal["selected", "auto", "suggest", "off"]
