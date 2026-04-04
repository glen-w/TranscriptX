"""Shared ordering and caps for group temporal overlay charts (cross-session readability)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence, Tuple

from transcriptx.core.pipeline.result_envelope import PerTranscriptResult

# Max member runs (sessions) drawn into one overlay chart — shared by acts / sentiment / pauses.
DEFAULT_MAX_GROUP_OVERLAY_SESSIONS = 8


def sort_per_transcript_results_for_overlay(
    results: Sequence[PerTranscriptResult],
) -> List[PerTranscriptResult]:
    """
    Stable ordering: ``order_index`` ascending, then transcript path stem.

    Matches group sentiment / pauses temporal contracts so "first N sessions" is never ambiguous.
    """
    decorated: List[Tuple[int, str, PerTranscriptResult]] = []
    for r in results:
        oi = r.order_index if isinstance(r.order_index, int) else 10**9
        stem = Path(r.transcript_path).stem
        decorated.append((oi, stem, r))
    decorated.sort(key=lambda t: (t[0], t[1]))
    return [t[2] for t in decorated]


def cap_per_transcript_results_for_overlay(
    results: Sequence[PerTranscriptResult],
    *,
    max_sessions: int = DEFAULT_MAX_GROUP_OVERLAY_SESSIONS,
) -> List[PerTranscriptResult]:
    """Return the first ``max_sessions`` results after canonical overlay ordering."""
    ordered = sort_per_transcript_results_for_overlay(results)
    return ordered[:max_sessions]
