"""Pydantic schema for analysis.keyphrases."""

from __future__ import annotations

from pydantic import BaseModel, Field


class KeyphrasesSettingsModel(BaseModel):
    enabled_methods: list[str] = Field(
        default_factory=lambda: ["noun_chunks", "yake", "keybert"]
    )
    max_phrases: int = Field(default=40, ge=1)
    min_phrase_tokens: int = Field(default=1, ge=1)
    max_phrase_tokens: int = Field(default=6, ge=1)
    min_occurrences_global: int = Field(default=2, ge=1)
    min_occurrences_speaker: int = Field(default=1, ge=1)
    diversity_jaccard_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    evidence_max_per_phrase: int = Field(default=3, ge=0)
    evidence_snippet_max_chars: int = Field(default=120, ge=0)
    keybert_model_id: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2"
    )
    yake_lan: str = Field(default="en")
    yake_n: int = Field(default=3, ge=1)
    yake_top: int = Field(default=40, ge=1)
    yake_window_size: int = Field(default=2, ge=1)
    min_member_sessions: int = Field(default=2, ge=1)
