"""System configuration classes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class LLMConfig:
    """
    LLM provider configuration.

    Provider/connection settings and generation limits are grouped here.
    Module-specific prompt behaviour lives with each analysis module.
    """

    # Provider / connection
    enabled: bool = False
    provider: str = "null"  # null | ollama
    model: str | None = None
    base_url: str | None = None
    request_timeout: float = 1350.0
    availability_timeout: float = 7.5

    # Generation defaults (callers pass explicit temperature to generate())
    seed: int = 42
    max_input_chars: int = 48_000
    max_output_tokens: int | None = 2048
    default_temperature: float = 0.3


@dataclass
class LoggingConfig:
    """
    Configuration for logging system.

    This class defines all logging-related settings including log levels,
    output formats, file handling, and rotation policies.

    Attributes:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: Format string for log messages
        file_logging: Whether to log to files in addition to console
        log_file: Name of the log file
        max_log_size: Maximum size of log file before rotation (in bytes)
        backup_count: Number of backup log files to keep
    """

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_logging: bool = True
    log_file: str = "transcriptx.log"
    max_log_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


# Preprocessing mode types (config layer: defaults for per-step and global behavior)
PreprocessingMode = Literal["auto", "suggest", "off"]
GlobalPreprocessingMode = Literal["selected", "auto", "suggest", "off"]


@dataclass
class AudioPreprocessingConfig:
    """
    Configuration for audio preprocessing settings (config layer).

    This dataclass defines **config-time defaults**: per-step and global modes
    that influence how apply_preprocessing() behaves when no run-time override
    is given. It is a different layer from the **request-time** contract used by
    PreprocessRequest.preprocessing_mode ("off" | "selected" | "auto"), which
    controls a single run. The workflow bridges the two: it uses
    preprocessing_mode to derive a per-step decisions dict, then passes that into
    apply_preprocessing() along with this config for numeric parameters (LUFS,
    cutoffs, etc.). See PreprocessRequest and _derive_decisions() in the
    preprocess workflow for the request → config bridge.

    Per-step modes (convert_to_mono, downsample, normalize_mode, denoise_mode, …):
    - "auto": Always apply if needed (no user interaction)
    - "suggest": Assess files and suggest to user, apply if confirmed
    - "off": Never apply this preprocessing step

    Global preprocessing_mode overrides all per-step settings when not "selected":
    - "selected": Use per-step mode settings (fine-grained control)
    - "auto": Override all steps to "auto"
    - "suggest": Override all steps to "suggest"
    - "off": Override all steps to "off"

    Attributes:
        preprocessing_mode: Global preprocessing control mode (default: "selected")
        convert_to_mono: Convert stereo to mono mode (default: "auto")
        downsample: Downsample to target sample rate mode (default: "auto")
        target_sample_rate: Target sample rate in Hz (default: 16000)
        skip_if_already_compliant: Skip processing if file already meets requirements (default: True)
        normalize_mode: Loudness normalization mode (default: "auto")
        target_lufs: Target loudness in LUFS (range: -20 to -16, default: -18.0)
        limiter_enabled: Enable peak limiter (default: True)
        limiter_peak_db: Peak limiter threshold in dB (default: -1.0)
        denoise_mode: Denoising mode (default: "suggest")
        denoise_strength: Denoising strength: "low", "medium", or "high" (default: "medium")
        highpass_mode: High-pass filter mode (default: "suggest")
        highpass_cutoff: High-pass filter cutoff in Hz (range: 70-100, default: 80)
        lowpass_mode: Low-pass filter mode (default: "off")
        lowpass_cutoff: Low-pass filter cutoff in Hz (default: 8000)
        bandpass_mode: Band-pass filter mode (default: "off")
        bandpass_low: Band-pass low cutoff in Hz (default: 300)
        bandpass_high: Band-pass high cutoff in Hz (default: 3400)
    """

    # Global preprocessing control
    preprocessing_mode: GlobalPreprocessingMode = (
        "selected"  # Override all per-step modes
    )

    # Core settings
    convert_to_mono: PreprocessingMode = "auto"
    downsample: PreprocessingMode = "auto"
    target_sample_rate: int = 16000
    skip_if_already_compliant: bool = True

    # Loudness normalization
    normalize_mode: PreprocessingMode = "auto"  # Renamed from normalize_enabled
    target_lufs: float = -18.0  # Range: -20 to -16
    limiter_enabled: bool = True
    limiter_peak_db: float = -1.0

    # Noise reduction
    denoise_mode: PreprocessingMode = "suggest"  # Renamed from denoise_enabled
    denoise_strength: Literal["low", "medium", "high"] = "medium"

    # Filtering (ASR-safe)
    highpass_mode: PreprocessingMode = "suggest"  # Renamed from highpass_enabled
    highpass_cutoff: int = 80  # Range: 70-100 Hz
    lowpass_mode: PreprocessingMode = "off"  # Renamed from lowpass_enabled
    lowpass_cutoff: int = 8000
    bandpass_mode: PreprocessingMode = "off"  # Renamed from bandpass_enabled
    bandpass_low: int = 300
    bandpass_high: int = 3400
