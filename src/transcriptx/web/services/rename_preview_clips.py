"""Deterministic diverse clip selection for the Rename Transcript page."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence

from transcriptx.io.speaker_map_resolver import (
    is_effective_speaker_name,
    normalize_diarized_id,
)
from transcriptx.services.speaker_studio.segment_index import SegmentInfo

UNKNOWN_SPEAKER_LABEL = "Unknown speaker"
_DEFAULT_LIMIT = 10
_WS_RE = re.compile(r"\s+")


def speaker_identity_key(seg: SegmentInfo) -> str:
    """Stable diarized identity — never group by effective display name."""
    did = (seg.speaker_diarized_id or "").strip()
    if did:
        return normalize_diarized_id(did) or did
    raw = (seg.speaker or "").strip()
    if raw:
        return normalize_diarized_id(raw) or raw
    return f"__missing_{seg.index}__"


def effective_rename_speaker_label(seg: SegmentInfo) -> str:
    """mapped display name → diarized ID → Unknown speaker."""
    did = (seg.speaker_diarized_id or "").strip()
    display = (seg.speaker or "").strip()
    if did and display and is_effective_speaker_name(did, display):
        return display
    if display:
        return display
    if did:
        return did
    return UNKNOWN_SPEAKER_LABEL


def _normalize_text(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").strip().casefold())


def _is_eligible(seg: SegmentInfo) -> bool:
    try:
        start = float(seg.start)
        end = float(seg.end)
    except (TypeError, ValueError):
        return False
    if start != start or end != end:  # NaN
        return False
    if end <= start:
        return False
    if not (seg.text or "").strip():
        return False
    return True


def _evenly_spaced_indices(n: int, k: int) -> list[int]:
    """Pick ``k`` indices from ``0..n-1`` with deterministic even spacing."""
    if n <= 0 or k <= 0:
        return []
    k = min(k, n)
    if k == 1:
        return [n // 2]
    if k == n:
        return list(range(n))
    return [int(i * (n - 1) / (k - 1)) for i in range(k)]


def _slot_counts(speaker_count: int, limit: int) -> list[int]:
    """Per-speaker slot counts in speaker order (length == speakers used)."""
    if speaker_count <= 0 or limit <= 0:
        return []
    if speaker_count >= limit:
        return [1] * limit
    base = limit // speaker_count
    rem = limit % speaker_count
    return [base + (1 if i < rem else 0) for i in range(speaker_count)]


def select_rename_preview_segments(
    segments: Sequence[SegmentInfo],
    *,
    limit: int = _DEFAULT_LIMIT,
) -> list[SegmentInfo]:
    """Select up to ``limit`` diverse clips; identical input → identical output."""
    if limit <= 0:
        return []

    eligible = [s for s in segments if _is_eligible(s)]
    if not eligible:
        return []

    by_speaker: dict[str, list[SegmentInfo]] = defaultdict(list)
    for seg in eligible:
        by_speaker[speaker_identity_key(seg)].append(seg)

    for key in by_speaker:
        by_speaker[key].sort(key=lambda s: (s.start, s.end, s.index))

    speaker_order = sorted(
        by_speaker.keys(),
        key=lambda key: (
            by_speaker[key][0].start,
            key,
            by_speaker[key][0].index,
        ),
    )

    counts = _slot_counts(len(speaker_order), limit)
    speakers_used = speaker_order[: len(counts)]

    primary: list[SegmentInfo] = []
    primary_ids: set[int] = set()
    for key, k in zip(speakers_used, counts):
        group = by_speaker[key]
        for idx in _evenly_spaced_indices(len(group), k):
            seg = group[idx]
            if seg.index in primary_ids:
                continue
            primary.append(seg)
            primary_ids.add(seg.index)

    accepted: list[SegmentInfo] = []
    accepted_ids: set[int] = set()
    seen_text: set[str] = set()
    for seg in sorted(primary, key=lambda s: (s.start, speaker_identity_key(s), s.index)):
        norm = _normalize_text(seg.text)
        if norm in seen_text:
            continue
        seen_text.add(norm)
        accepted.append(seg)
        accepted_ids.add(seg.index)

    if len(accepted) < limit:
        leftovers = sorted(
            (s for s in eligible if s.index not in accepted_ids),
            key=lambda s: (s.start, speaker_identity_key(s), s.index),
        )
        for seg in leftovers:
            if len(accepted) >= limit:
                break
            norm = _normalize_text(seg.text)
            if norm in seen_text:
                continue
            seen_text.add(norm)
            accepted.append(seg)
            accepted_ids.add(seg.index)

    accepted.sort(key=lambda s: (s.start, speaker_identity_key(s), s.index))
    return accepted[:limit]


def mapped_speaker_summary_labels(segments: Sequence[SegmentInfo]) -> list[str]:
    """Unique effective mapped display names from the same SegmentInfo set."""
    labels: list[str] = []
    seen: set[str] = set()
    for seg in segments:
        did = (seg.speaker_diarized_id or "").strip()
        display = (seg.speaker or "").strip()
        if not did or not display:
            continue
        if not is_effective_speaker_name(did, display):
            continue
        if display in seen:
            continue
        seen.add(display)
        labels.append(display)
    labels.sort(key=lambda s: s.casefold())
    return labels
