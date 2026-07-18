"""Language resolution for emotion-family modules."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

LANGUAGE_POLICY_V1 = "language_policy_v1"

_EN_ALIASES = frozenset({"en", "eng", "english", "en-us", "en-gb"})


def normalize_language_code(raw: str | None) -> str | None:
    if raw is None:
        return None
    code = str(raw).strip().casefold()
    if not code or code in {"auto", "unknown"}:
        return None
    return code


def is_english(code: str | None) -> bool:
    if code is None:
        return False
    return code in _EN_ALIASES or code.startswith("en-")


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
        return meta_lang, "transcript_metadata"

    return "en", "assumed_en_missing_metadata"
