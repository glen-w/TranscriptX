"""LLM output feedback (collect-only v1)."""

from __future__ import annotations

from transcriptx.core.llm_feedback.errors import (
    LlmFeedbackError,
    LlmFeedbackPathError,
    LlmFeedbackPersistenceError,
    LlmFeedbackValidationError,
)
from transcriptx.core.llm_feedback.models import (
    EVENT_SCHEMA_ID,
    NOTE_MAX_CODEPOINTS,
    REASONS_BY_RATING,
    FeedbackEvent,
    FeedbackProvenance,
    FeedbackRating,
    FeedbackReason,
    FeedbackSurface,
    FeedbackTarget,
    SubjectType,
    build_event,
    compute_output_sha256,
    compute_target_instance_id,
    normalize_note,
    reasons_for_rating,
)
from transcriptx.core.llm_feedback.service import LlmFeedbackService
from transcriptx.core.llm_feedback.store import FeedbackStore, IterEventsResult

__all__ = [
    "EVENT_SCHEMA_ID",
    "NOTE_MAX_CODEPOINTS",
    "REASONS_BY_RATING",
    "FeedbackEvent",
    "FeedbackProvenance",
    "FeedbackRating",
    "FeedbackReason",
    "FeedbackStore",
    "FeedbackSurface",
    "FeedbackTarget",
    "IterEventsResult",
    "LlmFeedbackError",
    "LlmFeedbackPathError",
    "LlmFeedbackPersistenceError",
    "LlmFeedbackService",
    "LlmFeedbackValidationError",
    "SubjectType",
    "build_event",
    "compute_output_sha256",
    "compute_target_instance_id",
    "normalize_note",
    "reasons_for_rating",
]
