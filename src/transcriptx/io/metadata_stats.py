"""Read-only transcript document stat resolution (metadata-first, no I/O).

``metadata.word_count`` is computed from all segment text via ``count_words()``.
Listing paths read metadata first; legacy fallback may compute from already-loaded
segments but must not load segments solely for stats.
"""

from __future__ import annotations

from typing import Any, Literal

from transcriptx.utils.text_utils import compute_word_count_from_segments

DurationCalculation = Literal["max_end", "span"]


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def duration_seconds_from_segments(
    segments: list[Any],
    *,
    method: DurationCalculation = "max_end",
) -> float:
    """Derive duration from in-memory segment dicts."""
    if not segments:
        return 0.0
    dict_segments = [seg for seg in segments if isinstance(seg, dict)]
    if not dict_segments:
        return 0.0
    if method == "span":
        ends = [float(seg.get("end", 0) or 0) for seg in dict_segments]
        starts = [float(seg.get("start", 0) or 0) for seg in dict_segments]
        if ends and starts:
            return max(ends) - min(starts)
        return 0.0
    return float(max((seg.get("end", 0) or 0) for seg in dict_segments))


def duration_seconds_from_document(
    doc: dict[str, Any],
    *,
    method: DurationCalculation = "max_end",
) -> float:
    """Read duration from metadata, else derive from loaded segments."""
    metadata = doc.get("metadata")
    if isinstance(metadata, dict):
        for key in ("duration_seconds", "duration"):
            value = _coerce_float(metadata.get(key))
            if value is not None:
                return value
    segments = doc.get("segments")
    if isinstance(segments, list):
        return duration_seconds_from_segments(segments, method=method)
    return 0.0


def word_count_from_document(
    doc: dict[str, Any],
    *,
    allow_segment_fallback: bool = True,
    allow_legacy_words_alias: bool = True,
) -> int:
    """Resolve word count metadata-first with optional in-memory segment fallback."""
    metadata = doc.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    word_count = _coerce_int(metadata.get("word_count"))
    if word_count is not None:
        return word_count
    if allow_legacy_words_alias:
        word_count = _coerce_int(metadata.get("words"))
        if word_count is not None:
            return word_count
    if allow_segment_fallback:
        segments = doc.get("segments")
        if isinstance(segments, list):
            return compute_word_count_from_segments(segments)
    return 0
