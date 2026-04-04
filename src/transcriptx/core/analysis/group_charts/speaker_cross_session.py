"""
Cross-session speaker series for group charts (sentiment, stats).

Uses ``CanonicalSpeakerMap`` + per-transcript module payloads — not merged ``speaker_rows``,
which lack per-session breakdown.

Session order: ``order_index`` ascending, then transcript path stem (matches overlay helpers).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from transcriptx.core.analysis.aggregation.rows import (
    _build_display_to_canonical,
    _fallback_canonical_id,
)
from transcriptx.core.analysis.aggregation.sentiment import _extract_sentiment_payload
from transcriptx.core.analysis.stats.aggregation import _extract_stats_payload
from transcriptx.core.analysis.group_charts.helpers import member_session_label
from transcriptx.core.analysis.group_charts.overlay_series import (
    sort_per_transcript_results_for_overlay,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


@dataclass(frozen=True)
class SentimentCrossSessionSeries:
    """One bar chart: compound_mean per session for one canonical speaker."""

    canonical_speaker_id: int
    display_name: str
    categories: Tuple[str, ...]
    values: Tuple[float, ...]


def collect_sentiment_cross_session_speaker_series(
    per_transcript_results: Sequence[PerTranscriptResult],
    transcript_set: TranscriptSet,
    canonical_speaker_map: CanonicalSpeakerMap,
) -> List[SentimentCrossSessionSeries]:
    """
    Per canonical speaker: ordered (session_label, compound_mean) for sessions where they
    appear in that transcript's sentiment ``speaker_stats``.

    Emits a series only when the speaker has **≥2** sessions with numeric ``compound_mean``.
    """
    ordered = sort_per_transcript_results_for_overlay(per_transcript_results)
    # bucket: canonical_id -> list of (label, compound_mean)
    raw: Dict[int, List[Tuple[str, float]]] = {}

    for result in ordered:
        if "sentiment" not in result.module_results:
            continue
        payload = _extract_sentiment_payload(result.module_results)
        speaker_stats = payload.get("speaker_stats")
        if not isinstance(speaker_stats, dict):
            continue
        display_to_canonical = _build_display_to_canonical(
            result.transcript_path, canonical_speaker_map
        )
        label = member_session_label(result, transcript_set)
        for speaker, stats in speaker_stats.items():
            if not isinstance(stats, dict):
                continue
            cid = display_to_canonical.get(speaker, _fallback_canonical_id(speaker))
            cm = stats.get("compound_mean")
            if not isinstance(cm, (int, float)) or isinstance(cm, bool):
                continue
            raw.setdefault(cid, []).append((label, float(cm)))

    out: List[SentimentCrossSessionSeries] = []
    for cid, points in raw.items():
        if len(points) < 2:
            continue
        display_name = str(
            canonical_speaker_map.canonical_to_display.get(cid, f"Speaker {cid}")
        )
        categories = tuple(p[0] for p in points)
        values = tuple(p[1] for p in points)
        out.append(
            SentimentCrossSessionSeries(
                canonical_speaker_id=cid,
                display_name=display_name,
                categories=categories,
                values=values,
            )
        )
    return out


@dataclass(frozen=True)
class StatsCrossSessionSeries:
    """One bar chart: word_count per session for one canonical speaker (stats v1)."""

    canonical_speaker_id: int
    display_name: str
    categories: Tuple[str, ...]
    values: Tuple[float, ...]


def collect_stats_cross_session_speaker_series(
    per_transcript_results: Sequence[PerTranscriptResult],
    transcript_set: TranscriptSet,
    canonical_speaker_map: CanonicalSpeakerMap,
) -> List[StatsCrossSessionSeries]:
    """
    Per canonical speaker: ordered (session_label, word_count) from stats ``speaker_stats``
    tuples. See ``docs/groups/group_charts_stats_cross_session_contract.md``.

    Emits a series only when the speaker has **≥2** sessions with numeric ``word_count``.
    """
    ordered = sort_per_transcript_results_for_overlay(per_transcript_results)
    raw: Dict[int, List[Tuple[str, float]]] = {}

    for result in ordered:
        if "stats" not in result.module_results:
            continue
        payload = _extract_stats_payload(result.module_results)
        speaker_stats = payload.get("speaker_stats")
        if not isinstance(speaker_stats, list):
            continue
        display_to_canonical = _build_display_to_canonical(
            result.transcript_path, canonical_speaker_map
        )
        label = member_session_label(result, transcript_set)
        for row in speaker_stats:
            if not isinstance(row, (list, tuple)) or len(row) < 3:
                continue
            name = row[1]
            word_count = row[2]
            if not isinstance(name, str):
                name = str(name)
            if not isinstance(word_count, (int, float)) or isinstance(word_count, bool):
                continue
            cid = display_to_canonical.get(name, _fallback_canonical_id(name))
            raw.setdefault(cid, []).append((label, float(word_count)))

    out: List[StatsCrossSessionSeries] = []
    for cid, points in raw.items():
        if len(points) < 2:
            continue
        display_name = str(
            canonical_speaker_map.canonical_to_display.get(cid, f"Speaker {cid}")
        )
        categories = tuple(p[0] for p in points)
        values = tuple(p[1] for p in points)
        out.append(
            StatsCrossSessionSeries(
                canonical_speaker_id=cid,
                display_name=display_name,
                categories=categories,
                values=values,
            )
        )
    return out


def collect_stats_cross_session_speaker_segment_count_series(
    per_transcript_results: Sequence[PerTranscriptResult],
    transcript_set: TranscriptSet,
    canonical_speaker_map: CanonicalSpeakerMap,
) -> List[StatsCrossSessionSeries]:
    """
    Per canonical speaker: ordered (session_label, segment_count) from stats
    ``speaker_stats`` tuples (index 3). See v2 in
    ``docs/groups/group_charts_stats_cross_session_contract.md``.

    Emits a series only when the speaker has **≥2** sessions with numeric
    ``segment_count``.
    """
    ordered = sort_per_transcript_results_for_overlay(per_transcript_results)
    raw: Dict[int, List[Tuple[str, float]]] = {}

    for result in ordered:
        if "stats" not in result.module_results:
            continue
        payload = _extract_stats_payload(result.module_results)
        speaker_stats = payload.get("speaker_stats")
        if not isinstance(speaker_stats, list):
            continue
        display_to_canonical = _build_display_to_canonical(
            result.transcript_path, canonical_speaker_map
        )
        label = member_session_label(result, transcript_set)
        for row in speaker_stats:
            if not isinstance(row, (list, tuple)) or len(row) < 4:
                continue
            name = row[1]
            seg_count = row[3]
            if not isinstance(name, str):
                name = str(name)
            if not isinstance(seg_count, (int, float)) or isinstance(seg_count, bool):
                continue
            cid = display_to_canonical.get(name, _fallback_canonical_id(name))
            raw.setdefault(cid, []).append((label, float(seg_count)))

    out: List[StatsCrossSessionSeries] = []
    for cid, points in raw.items():
        if len(points) < 2:
            continue
        display_name = str(
            canonical_speaker_map.canonical_to_display.get(cid, f"Speaker {cid}")
        )
        categories = tuple(p[0] for p in points)
        values = tuple(p[1] for p in points)
        out.append(
            StatsCrossSessionSeries(
                canonical_speaker_id=cid,
                display_name=display_name,
                categories=categories,
                values=values,
            )
        )
    return out
