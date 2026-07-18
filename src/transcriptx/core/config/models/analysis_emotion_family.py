"""Pydantic settings for emotion-family modules."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EmotionLexicalSettingsModel(BaseModel):
    """analysis.emotion.* lexical settings."""

    # Zero is deliberately valid for coverage/warn thresholds.
    low_coverage_threshold: float = Field(default=0.05, ge=0.0)
    no_hit_rate_warn: float = Field(default=0.8, ge=0.0)


class ContextualEmotionSettingsModel(BaseModel):
    """analysis.contextual_emotion.* — experimental until Phase 5."""

    profile_id: str = Field(default="contextual_hartmann_distilroberta_v1")
    # Zero confidence threshold is deliberately supported.
    confidence_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    batch_size: int = Field(default=8, ge=1)
    release_channel: str = Field(default="experimental")


class FineGrainedEmotionSettingsModel(BaseModel):
    """analysis.fine_grained_emotion.* — experimental until Phase 5."""

    profile_id: str = Field(default="fine_grained_samlowe_go_emotions_v1")
    # Zero label threshold is deliberately supported.
    label_threshold: float = Field(default=0.28, ge=0.0, le=1.0)
    max_labels_per_segment: int = Field(default=3, ge=0)
    batch_size: int = Field(default=8, ge=1)
    release_channel: str = Field(default="experimental")


class EmotionFamilyAliasConflictError(ValueError):
    """Raised when legacy and namespaced emotion keys conflict."""


def validate_emotion_family_aliases(
    *,
    legacy_emotion_model_name: str | None,
    contextual_profile_id: str | None,
    legacy_explicitly_set: bool = False,
    nested_explicitly_set: bool = False,
) -> None:
    """
    New namespaced keys win only when legacy is absent.

    Both present with conflicting values → configuration validation failure.
    Equivalent values → accept.
    """
    if not (legacy_explicitly_set and nested_explicitly_set):
        return
    legacy = (legacy_emotion_model_name or "").strip()
    nested = (contextual_profile_id or "").strip()
    if not legacy or not nested:
        return
    # Legacy stores a Hub model id; nested stores a profile_id. Treat a
    # direct string equality as "equivalent"; otherwise reject conflicts.
    if legacy != nested and legacy not in nested and nested not in legacy:
        raise EmotionFamilyAliasConflictError(
            "Conflicting emotion configuration: "
            f"analysis.emotion_model_name={legacy!r} vs "
            f"analysis.contextual_emotion.profile_id={nested!r}. "
            "Set only one, or make them agree."
        )
