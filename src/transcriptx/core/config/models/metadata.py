"""Pydantic schema for metadata.* settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MetadataSettingsModel(BaseModel):
    """Canonical field definitions for transcript metadata configuration."""

    duration_calculation: Literal["max_end", "span"] = Field(
        default="max_end",
        description="How duration_seconds is derived from segments when recomputing metadata.",
    )
    listing_word_count_fallback: Literal["in_memory", "metadata_only"] = Field(
        default="in_memory",
        description=(
            "Whether listing views may scan loaded segments for word_count when metadata is absent."
        ),
    )
    auto_refresh_on_write: bool = Field(
        default=True,
        description="Recompute derived transcript metadata on TranscriptStore writes.",
    )
    legacy_words_alias: bool = Field(
        default=True,
        description="Accept legacy metadata.words as a word_count alias when reading documents.",
    )
