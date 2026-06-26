"""Metadata helpers for transcript viewer metrics."""

from __future__ import annotations

from typing import Any

from transcriptx.utils.text_utils import compute_word_count_from_segments


def speaker_tooltip(segments: list[dict[str, Any]]) -> str | None:
    """Build tooltip listing unique speaker names."""
    speaker_names: list[str] = []
    try:
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            name = seg.get("speaker_display") or seg.get("speaker")
            if not name:
                continue
            speaker_names.append(str(name).strip())
    except Exception:
        return None
    unique = sorted({n for n in speaker_names if n})
    if not unique:
        return None
    return "Speakers:\n" + "\n".join(f"- {name}" for name in unique)


def segment_word_stats(segments: list[dict[str, Any]]) -> tuple[int, int, float]:
    """Return segment count, total words, and avg words per segment."""
    seg_count = len(segments)
    try:
        total_words = compute_word_count_from_segments(segments)
    except Exception:
        total_words = 0
    avg_words = (total_words / seg_count) if seg_count else 0.0
    return seg_count, total_words, avg_words
