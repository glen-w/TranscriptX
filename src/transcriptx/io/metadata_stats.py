"""Read-only transcript document stat resolution (metadata-first, no I/O).

``metadata.word_count`` is computed from all segment text via ``count_words()``.
Listing paths read metadata first; legacy fallback may compute from already-loaded
segments but must not load segments solely for stats.
"""

from __future__ import annotations

from typing import Any, Literal

from transcriptx.io.metadata_display_options import MetadataConfig, get_metadata_config
from transcriptx.utils.text_utils import compute_word_count_from_segments

DurationCalculation = Literal["max_end", "span"]

DEFAULT_SESSION_STATS: dict[str, int | float] = {
    "segment_count": 0,
    "duration_seconds": 0,
    "duration_minutes": 0,
    "speaker_count": 0,
    "word_count": 0,
}


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


def _coerce_stat_number(value: Any, *, as_int: bool = False) -> int | float | None:
    try:
        if as_int:
            return int(value)
        return float(value)
    except (TypeError, ValueError):
        return None


def duration_seconds_from_segments(
    segments: list[Any],
    *,
    method: DurationCalculation = "max_end",
) -> float:
    """Derive duration from in-memory segment dicts.

    This is **not** the same contract as
    ``optional_span_duration_seconds_from_segments``:

    - ``max_end`` (default): latest segment end timestamp; returns ``0.0`` when
      segments are empty.
    - ``span``: ``max(end) - min(start)`` without strict pair validation;
      returns ``0.0`` when segments are empty.

    For library-style duration that skips invalid pairs and returns ``None`` when
    no valid timestamps exist, use ``optional_span_duration_seconds_from_segments``.
    """
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


def optional_span_duration_seconds_from_segments(
    segments: list[Any],
) -> float | None:
    """Span duration from valid segment pairs; ``None`` when none are usable.

    **Not interchangeable** with ``duration_seconds_from_segments``:

    - Uses strict pair validation (numeric start/end, ``end >= start``).
    - Computes ``max(end) - min(start)`` over valid pairs only.
    - Returns ``None`` (not ``0.0``) when no valid pairs exist.

    Example: segments ``[1–3, 4–8.5]`` → ``7.5`` here, but ``8.5`` with
    ``duration_seconds_from_segments(..., method="max_end")``.
    """
    times: list[tuple[float, float]] = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        try:
            start = float(seg.get("start"))
            end = float(seg.get("end"))
        except (TypeError, ValueError):
            continue
        if end >= start:
            times.append((start, end))
    if not times:
        return None
    min_start = min(start for start, _ in times)
    max_end = max(end for _, end in times)
    duration = max_end - min_start
    return duration if duration >= 0 else None


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


def listing_stats_from_document(
    doc: dict[str, Any],
    *,
    meta_cfg: MetadataConfig | None = None,
) -> dict[str, int | float]:
    """Map document.metadata to session listing stats.

    Word count is metadata-first; legacy fallback uses in-memory segments only
    when the document is already loaded — never loads segments solely for stats.
    """
    stats = dict(DEFAULT_SESSION_STATS)

    metadata = doc.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    segment_count = _coerce_stat_number(metadata.get("segment_count"), as_int=True)
    if segment_count is None:
        segment_count = _coerce_stat_number(metadata.get("segments"), as_int=True)
    if segment_count is not None:
        stats["segment_count"] = segment_count

    duration_seconds = _coerce_stat_number(metadata.get("duration_seconds"))
    if duration_seconds is None:
        duration_seconds = _coerce_stat_number(metadata.get("duration"))
    if duration_seconds is not None:
        stats["duration_seconds"] = duration_seconds
        stats["duration_minutes"] = round(duration_seconds / 60, 1)

    speaker_count = _coerce_stat_number(metadata.get("speaker_count"), as_int=True)
    if speaker_count is None:
        speaker_count = _coerce_stat_number(metadata.get("num_speakers"), as_int=True)
    if speaker_count is not None:
        stats["speaker_count"] = speaker_count

    cfg = meta_cfg if meta_cfg is not None else get_metadata_config()
    stats["word_count"] = word_count_from_document(
        doc,
        allow_segment_fallback=cfg.listing_word_count_fallback == "in_memory",
        allow_legacy_words_alias=cfg.legacy_words_alias,
    )

    return stats
