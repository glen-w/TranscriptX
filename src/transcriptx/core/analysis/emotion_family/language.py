"""Language resolution for emotion-family modules."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from transcriptx.core.analysis.language_routing import (
    TAG_ASSUMED_EN,
    TAG_TRANSCRIPT_METADATA,
    is_english,
    normalize_language_code,
)

__all__ = [
    "LANGUAGE_POLICY_V1",
    "extract_transcript_metadata",
    "is_english",
    "normalize_language_code",
    "resolve_segment_language",
]

LANGUAGE_POLICY_V1 = "language_policy_v1"


def extract_transcript_metadata(
    segments: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """
    Central metadata acquisition used by lexical and classifier modules.

    Prefers ``_transcript_metadata`` attached to the first segment (common
    loader pattern). Returns an empty dict when unavailable.
    """
    if not segments:
        return {}
    meta = segments[0].get("_transcript_metadata")
    if isinstance(meta, dict):
        return dict(meta)
    return {}


def resolve_segment_language(
    segment: Mapping[str, Any],
    transcript_metadata: Mapping[str, Any] | None = None,
) -> tuple[str | None, str]:
    """
    Return (resolved_code_or_None, language_resolution_tag).

    Order: segment language → transcript metadata.language → assumed English.
    """
    seg_lang = normalize_language_code(
        segment.get("language") if segment is not None else None
    )
    if seg_lang is not None:
        return seg_lang, "segment_override"

    meta = transcript_metadata or {}
    meta_lang = normalize_language_code(meta.get("language"))
    if meta_lang is not None:
        return meta_lang, TAG_TRANSCRIPT_METADATA

    return "en", TAG_ASSUMED_EN
