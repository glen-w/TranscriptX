"""P1 multilingual model routing (infrastructure).

First consumer: NER skips with ``unsupported_language`` when metadata language
is not English. Other modules adopt later; this is not a multilingual product
claim.
"""

from __future__ import annotations

from typing import Any, Mapping

from transcriptx.core.analysis.emotion_family.language import (
    is_english,
    normalize_language_code,
)

SPACY_EN_MODELS = ("en_core_web_md", "en_core_web_sm")


def resolve_language(metadata: Mapping[str, Any] | None) -> str | None:
    if not metadata:
        return None
    return normalize_language_code(metadata.get("language"))


def spacy_model_for_language(language: str | None) -> str | None:
    """Return a spaCy model id, or None when the language is unsupported."""
    if language is None or is_english(language):
        return SPACY_EN_MODELS[0]
    return None
