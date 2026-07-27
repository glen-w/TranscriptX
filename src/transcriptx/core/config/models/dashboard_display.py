"""Pydantic schema for dashboard / transcript display settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DashboardDisplaySettingsModel(BaseModel):
    """Canonical field definitions for dashboard and transcript display knobs."""

    duration_hours_threshold_seconds: int = Field(
        default=3600,
        ge=1,
        description="Seconds at or above which compact duration display switches to hours+minutes.",
    )
    duration_summary_style: Literal["compact", "minutes_only"] = Field(
        default="compact",
        description="Duration summary formatting style for library and statistics views.",
    )
    transcript_exclude_unnamed_speakers: bool = Field(
        default=True,
        description=(
            "When true, the Transcript viewer hides segments whose speaker label is "
            "still a diarization placeholder (e.g. SPEAKER_02) rather than a mapped name."
        ),
    )
