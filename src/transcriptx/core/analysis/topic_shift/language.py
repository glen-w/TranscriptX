"""Language resolution for topic_shift backend selection."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from transcriptx.core.analysis.topic_shift.semantics import ENGLISH_CODES, BackendId


def normalize_language_code(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip().lower().replace("_", "-")
    if not text:
        return None
    # take primary subtag
    primary = text.split("-", 1)[0]
    return primary or None


def resolve_transcript_language(
    segments: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any] | None = None,
) -> tuple[Optional[str], str]:
    """
    Resolve once for the full transcript.

    Returns (code_or_None, resolution_tag).
    Mixed non-English segment overrides → treat as non-English (multilingual/TF-IDF path).
    """
    meta = metadata or {}
    meta_lang = normalize_language_code(
        meta.get("language") if isinstance(meta, Mapping) else None
    )

    seg_langs: list[str] = []
    for seg in segments:
        if not isinstance(seg, Mapping):
            continue
        code = normalize_language_code(seg.get("language"))
        if code:
            seg_langs.append(code)

    unique = sorted(set(seg_langs))
    if len(unique) > 1:
        # Mixed languages → not English-only MiniLM
        if all(u in ENGLISH_CODES for u in unique):
            return "en", "mixed_english_variants"
        return unique[0], "mixed_segment_languages"

    if len(unique) == 1:
        return unique[0], "segment_language"

    if meta_lang:
        return meta_lang, "transcript_metadata"

    return "en", "assumed_english"


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
    if is_english and resolution_tag != "mixed_segment_languages":
        if transformers_available:
            return "transformers_en", False
        return "tfidf", False

    # Non-English or mixed
    if multilingual_available:
        return "transformers_multi", False
    return "tfidf", True
