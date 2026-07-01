"""Pydantic schema for output settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from transcriptx.core.utils.paths import (
    DIARISED_TRANSCRIPTS_DIR,
    OUTPUTS_DIR,
    READABLE_TRANSCRIPTS_DIR,
    RECORDINGS_DIR,
)

DynamicMode = Literal["auto", "on", "off"]


class OutputSettingsModel(BaseModel):
    """Canonical field definitions for output paths and artifact generation."""

    base_output_dir: str = Field(default_factory=lambda: str(OUTPUTS_DIR))
    create_subdirectories: bool = Field(default=True)
    overwrite_existing: bool = Field(default=False)
    dynamic_charts: DynamicMode = Field(
        default="auto",
        description="Dynamic chart generation mode.",
    )
    dynamic_views: DynamicMode = Field(
        default="auto",
        description="Dynamic HTML view generation mode.",
    )
    default_audio_folder: str = Field(default_factory=lambda: str(RECORDINGS_DIR))
    default_transcript_folder: str = Field(
        default_factory=lambda: str(DIARISED_TRANSCRIPTS_DIR)
    )
    default_readable_transcript_folder: str = Field(
        default_factory=lambda: str(READABLE_TRANSCRIPTS_DIR)
    )
    audio_deduplication_threshold: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
    )
