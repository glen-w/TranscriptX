"""Shared type definitions for audio preprocessing and analysis."""

from __future__ import annotations

from typing import Optional

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict  # type: ignore[assignment]


class AudioMetrics(TypedDict, total=False):
    """Raw acoustic metrics produced by noise assessment."""

    rms_db: float
    peak_db: float
    clipping_percentage: float
    dc_offset_db: float
    zero_crossing_rate: float
    speech_ratio: Optional[float]
    snr_proxy_db: Optional[float]


class AudioAssessment(TypedDict, total=False):
    """Result of assess_audio_noise — noise level, suggested steps, and raw metrics."""

    noise_level: str  # "low" | "medium" | "high"
    suggested_steps: list[str]
    confidence: float
    metrics: AudioMetrics


class AudioCompliance(TypedDict, total=False):
    """Result of check_audio_compliance — whether a file already meets ASR requirements."""

    is_compliant: bool
    details: dict  # type: ignore[type-arg]
    missing_requirements: list[str]


class AudioFileMeta(TypedDict):
    """Basic file-level metadata returned by RecordingsService.get_audio_metadata."""

    duration_sec: float
    sample_rate: int
    channels: int
    format: str
    file_size_mb: float
