"""Shared language primitives and P1 multilingual model routing (infrastructure).

Owns the language-code rules used across analysis modules. Two normalisers
exist on purpose and are not interchangeable:

- ``normalize_language_code`` keeps region subtags (``en-us``); used for
  per-segment resolution (emotion family, NER).
- ``primary_language_subtag`` reduces to the primary subtag (``en-US`` -> ``en``);
  used by ``resolve_transcript_language``, the one whole-transcript policy
  (topic_shift, lexicon markers).

Both treat ``auto``/``unknown`` as missing.

First routing consumer: NER skips with ``unsupported_language`` when metadata
language is not English. This is not a multilingual product claim.
"""

from __future__ import annotations

from typing import Any, Final, Mapping, Sequence

SPACY_EN_MODELS = ("en_core_web_md", "en_core_web_sm")

ENGLISH_CODES: Final = frozenset({"en", "eng", "en-us", "en-gb", "en_us", "en_gb"})

_EN_ALIASES = frozenset({"en", "eng", "english", "en-us", "en-gb"})
_MISSING_LANGUAGE_CODES = frozenset({"auto", "unknown"})

# Resolution tags written to artifacts (``language_resolution``).
TAG_TRANSCRIPT_METADATA: Final = "transcript_metadata"
TAG_ASSUMED_EN: Final = "assumed_en_missing_metadata"
TAG_SEGMENT_LANGUAGE: Final = "segment_language"
TAG_MIXED_ENGLISH_VARIANTS: Final = "mixed_english_variants"
TAG_MIXED_SEGMENT_LANGUAGES: Final = "mixed_segment_languages"


def normalize_language_code(raw: str | None) -> str | None:
    if raw is None:
        return None
    code = str(raw).strip().casefold()
    if not code or code in _MISSING_LANGUAGE_CODES:
        return None
    return code


def is_english(code: str | None) -> bool:
    if code is None:
        return False
    return code in _EN_ALIASES or code.startswith("en-")


def primary_language_subtag(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip().lower().replace("_", "-")
    if not text or text in _MISSING_LANGUAGE_CODES:
        return None
    primary = text.split("-", 1)[0]
    return primary or None


def collect_segment_languages(segments: Sequence[Mapping[str, Any]]) -> list[str]:
    """Sorted unique primary subtags declared on segment ``language`` fields."""
    codes: set[str] = set()
    for seg in segments:
        if not isinstance(seg, Mapping):
            continue
        code = primary_language_subtag(seg.get("language"))
        if code:
            codes.add(code)
    return sorted(codes)


def resolve_transcript_language(
    segments: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    """
    Resolve one language for the whole transcript.

    Returns ``(primary_subtag, resolution_tag)``. Order: segment ``language``
    fields → ``metadata['language']`` → assumed English. Segments that disagree
    resolve to the first code alphabetically, tagged as mixed, unless every
    code is an English alias.
    """
    unique = collect_segment_languages(segments)
    if len(unique) > 1:
        if all(code in ENGLISH_CODES for code in unique):
            return "en", TAG_MIXED_ENGLISH_VARIANTS
        return unique[0], TAG_MIXED_SEGMENT_LANGUAGES
    if unique:
        return unique[0], TAG_SEGMENT_LANGUAGE

    meta_lang = primary_language_subtag(
        metadata.get("language") if isinstance(metadata, Mapping) else None
    )
    if meta_lang:
        return meta_lang, TAG_TRANSCRIPT_METADATA
    return "en", TAG_ASSUMED_EN


def resolve_language(metadata: Mapping[str, Any] | None) -> str | None:
    if not metadata:
        return None
    return normalize_language_code(metadata.get("language"))


def spacy_model_for_language(language: str | None) -> str | None:
    """Return a spaCy model id, or None when the language is unsupported."""
    if language is None or is_english(language):
        return SPACY_EN_MODELS[0]
    return None
