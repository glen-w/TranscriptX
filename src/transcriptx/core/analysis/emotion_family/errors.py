"""Typed errors for emotion-family persistence and generation integrity."""

from __future__ import annotations


class EmotionFamilyPersistError(RuntimeError):
    """Canonical generational persistence failed; module must not report success."""


class EmotionFamilyGenerationExistsError(EmotionFamilyPersistError):
    """Generation directory already exists; immutable IDs must not be reused."""


class EmotionFamilyGenerationConflictError(EmotionFamilyGenerationExistsError):
    """Existing generation contents conflict with the intended payload."""


class EmotionFamilyGenerationIncompleteError(EmotionFamilyPersistError):
    """Generation directory exists but is incomplete or unreadable."""


class EmotionFamilyGenerationValidationError(EmotionFamilyPersistError):
    """Rows or manifest failed pre-activation validation."""


class EmotionFamilyUnsafeIdentifierError(EmotionFamilyPersistError):
    """Generation ID, module ID, or cache key failed safe-identifier checks."""


class EmotionFamilySchemaError(EmotionFamilyPersistError):
    """Unknown or mismatched schema version."""
