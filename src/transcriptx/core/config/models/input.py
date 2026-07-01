"""Pydantic schema for input settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from transcriptx.core.utils.paths import RECORDINGS_DIR

FileSelectionMode = Literal["prompt", "explore", "direct"]


class InputSettingsModel(BaseModel):
    """Canonical field definitions for input discovery and file selection."""

    wav_folders: list[str] = Field(
        default_factory=lambda: ["/Volumes/DVT1600/RECORD/A"]
    )
    recordings_folders: list[str] = Field(default_factory=lambda: [str(RECORDINGS_DIR)])
    prefill_rename_with_date_prefix: bool = Field(default=True)
    file_selection_mode: FileSelectionMode = Field(default="prompt")
    playback_skip_seconds_short: float = Field(default=10.0)
    playback_skip_seconds_long: float = Field(default=60.0)
