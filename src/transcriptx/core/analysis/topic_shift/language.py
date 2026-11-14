"""Backend selection by language for topic_shift."""

from __future__ import annotations

from transcriptx.core.analysis.language_routing import (
    TAG_MIXED_SEGMENT_LANGUAGES,
    resolve_transcript_language,
)
from transcriptx.core.analysis.topic_shift.semantics import ENGLISH_CODES, BackendId

__all__ = ["resolve_transcript_language", "select_backend"]


def select_backend(
    language_code: str | None,
    resolution_tag: str,
    *,
    transformers_available: bool,
    multilingual_available: bool,
) -> tuple[BackendId, bool]:
    """
    Returns (preferred_backend, limited_language_support).

    English → transformers_en when available else tfidf.
    Known non-English → transformers_multi when available else tfidf (limited support).
    """
    code = (language_code or "en").lower()
    is_english = code in ENGLISH_CODES
    if is_english and resolution_tag != TAG_MIXED_SEGMENT_LANGUAGES:
        if transformers_available:
            return "transformers_en", False
        return "tfidf", False

    # Non-English or mixed
    if multilingual_available:
        return "transformers_multi", False
    return "tfidf", True
