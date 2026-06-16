"""Flat filename conventions for language-variant transcripts."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.utils.transcript_languages import (
    LANGUAGE_CODE_RE,
    normalize_language_code,
)


def parse_flat_language_variant_stem(stem: str) -> tuple[str, str] | None:
    """Parse ``{base}_{lang}`` stem into base name and two-letter language code.

    Returns None when the stem is not a flat language variant (e.g. ``meeting``,
    ``meeting_auto``, ``meeting_french``).
    """
    if not stem or "_" not in stem:
        return None
    base, lang_suffix = stem.rsplit("_", 1)
    if not base:
        return None
    language_code = normalize_language_code(lang_suffix)
    if language_code is None:
        return None
    if not LANGUAGE_CODE_RE.fullmatch(language_code):
        return None
    return base, language_code


def base_transcript_path_for_flat_variant(variant_path: Path) -> Path | None:
    """Return the base transcript path for a flat language variant, if parseable."""
    parsed = parse_flat_language_variant_stem(variant_path.stem)
    if parsed is None:
        return None
    base_stem, _language_code = parsed
    base_path = variant_path.parent / f"{base_stem}.json"
    try:
        if base_path.resolve() == Path(variant_path).resolve():
            return None
    except OSError:
        if base_path == variant_path:
            return None
    return base_path
