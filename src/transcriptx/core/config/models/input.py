"""Pydantic schema for input settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from transcriptx.core.utils.paths import RECORDINGS_DIR

FileSelectionMode = Literal["prompt", "explore", "direct"]
SmartRenameMode = Literal[
    "auto_import",
    "suggest_import",
    "suggest_rename_only",
    "off",
]


class InputSettingsModel(BaseModel):
    """Canonical field definitions for input discovery and file selection."""

    wav_folders: list[str] = Field(
        default_factory=lambda: ["/Volumes/DVT1600/RECORD/A"]
    )
    recordings_folders: list[str] = Field(default_factory=lambda: [str(RECORDINGS_DIR)])
    prefill_rename_with_date_prefix: bool = Field(default=True)
    smart_rename_mode: SmartRenameMode = Field(default="suggest_import")
    smart_rename_pattern: str = Field(default="{yymmdd}_{period}_{n}")
    file_selection_mode: FileSelectionMode = Field(default="prompt")
    playback_skip_seconds_short: float = Field(default=10.0)
    playback_skip_seconds_long: float = Field(default=60.0)
