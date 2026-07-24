"""Typed errors for LLM feedback."""

from __future__ import annotations


class LlmFeedbackError(Exception):
    """Base error for LLM feedback."""


class LlmFeedbackValidationError(LlmFeedbackError, ValueError):
    """Event failed strict validation."""


class LlmFeedbackPathError(LlmFeedbackError, ValueError):
    """Store path safety violation (symlink, escape, non-regular)."""


class LlmFeedbackPersistenceError(LlmFeedbackError, OSError):
    """Durable append failed (permissions, IO, lock)."""
