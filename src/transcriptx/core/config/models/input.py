"""Pydantic schema for input settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from transcriptx.core.config.models.llm_summary import LLMSummaryEffort
from transcriptx.core.utils.paths import RECORDINGS_DIR

FileSelectionMode = Literal["prompt", "explore", "direct"]
SmartRenameMode = Literal[
    "auto_import",
    "suggest_import",
    "suggest_rename_only",
    "off",
]
RenameContentSuggestionsMode = Literal["off", "auto"]
RenameDefaultCase = Literal["title", "upper", "lower"]


class InputSettingsModel(BaseModel):
    """Canonical field definitions for input discovery and file selection."""

    wav_folders: list[str] = Field(
        default_factory=lambda: ["/Volumes/DVT1600/RECORD/A"]
    )
    recordings_folders: list[str] = Field(default_factory=lambda: [str(RECORDINGS_DIR)])
    prefill_rename_with_date_prefix: bool = Field(default=True)
    smart_rename_mode: SmartRenameMode = Field(default="suggest_import")
    smart_rename_pattern: str = Field(default="{yymmdd}_{period}_{n}")
    rename_content_suggestions: RenameContentSuggestionsMode = Field(default="off")
    rename_default_case: RenameDefaultCase = Field(
        default="lower",
        description=(
            "Default case for rename token buttons and the new file name field "
            "(title / upper / lower)."
        ),
    )
    rename_suggest_transcript: bool = Field(default=True)
    rename_suggest_llm: bool = Field(default=False)
    rename_suggest_web: bool = Field(default=False)
    rename_suggestions_effort: LLMSummaryEffort = Field(
        default="low",
        description=(
            "Effort tier for rename-suggestion LLM when llm.provider is ollama. "
            "Controls max_input_chars, request_timeout, and max_output_tokens for "
            "that pass only. Model is chosen under Settings → Models for consumer "
            "rename_suggestions."
        ),
    )
    file_selection_mode: FileSelectionMode = Field(default="prompt")
    playback_skip_seconds_short: float = Field(default=10.0)
    playback_skip_seconds_long: float = Field(default=60.0)
