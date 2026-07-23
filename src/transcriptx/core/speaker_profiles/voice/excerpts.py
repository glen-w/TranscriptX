"""Frozen voice_quality.v1 excerpt construction (deterministic, no optional filters)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from transcriptx.core.speaker_profiles.voice.versioning import QUALITY_POLICY_ID

# voice_quality.v1 constants — changing any requires a new quality_policy_id.
MAX_MERGE_GAP_S = 0.25
MAX_OTHER_OVERLAP_S = 0.15
MIN_EXCERPT_S = 1.5
MAX_EXCERPT_S = 8.0
PAD_S = 0.05
MAX_EXCERPTS = 5
MIN_CENTRE_GAP_S = 2.0
NEAR_DUPLICATE_IOU = 0.8
MIN_TOTAL_UNION_SPEECH_S = 8.0


@dataclass(frozen=True)
class TimeInterval:
    start: float
    end: float
    segment_index: int = 0

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def centre(self) -> float:
        return (self.start + self.end) / 2.0


@dataclass(frozen=True)
class ExcerptPlan:
    """Selected clip window in seconds (source audio timeline)."""

    start: float
    end: float
    source_segment_indexes: tuple[int, ...]

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def start_us(self) -> int:
        return int(round(self.start * 1_000_000))

    @property
    def end_us(self) -> int:
        return int(round(self.end * 1_000_000))


@dataclass(frozen=True)
class ExcerptSelectionResult:
    quality_policy_id: str
    union_speech_duration_s: float
    excerpts: tuple[ExcerptPlan, ...]
    one_excerpt_fallback: bool
    outcome: str  # ok | insufficient_speech | no_eligible_clips


def _finite_float(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if x != x or x in (float("inf"), float("-inf")):
        return None
    return x


def _parse_speaker_intervals(
    segments: Sequence[Mapping[str, Any]],
    *,
    local_speaker_key: str,
    normalize_speaker,
) -> tuple[list[TimeInterval], list[TimeInterval]]:
    """Return (target_intervals, other_intervals) sorted by start, end, index."""
    target: list[TimeInterval] = []
    other: list[TimeInterval] = []
    for idx, seg in enumerate(segments):
        raw = seg.get("speaker")
        if raw is None:
            continue
        key = normalize_speaker(str(raw))
        if not key:
            continue
        start = _finite_float(seg.get("start"))
        end = _finite_float(seg.get("end"))
        if start is None or end is None or end <= start:
            continue
        interval = TimeInterval(start=start, end=end, segment_index=idx)
        if key == local_speaker_key:
            target.append(interval)
        else:
            other.append(interval)
    target.sort(key=lambda i: (i.start, i.end, i.segment_index))
    other.sort(key=lambda i: (i.start, i.end, i.segment_index))
    return target, other


def _gap_clear_of_others(
    gap_start: float, gap_end: float, others: Sequence[TimeInterval]
) -> bool:
    """True when no other-speaker interval intersects (gap_start, gap_end)."""
    if gap_end <= gap_start:
        return True
    for o in others:
        if o.end <= gap_start:
            continue
        if o.start >= gap_end:
            break
        if _overlap_amount(
            TimeInterval(start=gap_start, end=gap_end), o
        ) > 0.0:
            return False
    return True


def _merge_same_speaker(
    intervals: list[TimeInterval], others: list[TimeInterval]
) -> list[TimeInterval]:
    """Merge adjacent same-speaker intervals if gap ≤ MAX_MERGE_GAP_S.

    Never bridges across another speaker (gap must be clear of others).
    """
    if not intervals:
        return []
    merged: list[TimeInterval] = [intervals[0]]
    for nxt in intervals[1:]:
        cur = merged[-1]
        gap = nxt.start - cur.end
        if gap <= MAX_MERGE_GAP_S and _gap_clear_of_others(cur.end, nxt.start, others):
            merged[-1] = TimeInterval(
                start=cur.start,
                end=max(cur.end, nxt.end),
                segment_index=cur.segment_index,
            )
        else:
            merged.append(nxt)
    return merged


def _union_duration(intervals: Sequence[TimeInterval]) -> float:
    if not intervals:
        return 0.0
    total = 0.0
    cur_s, cur_e = intervals[0].start, intervals[0].end
    for iv in intervals[1:]:
        if iv.start <= cur_e:
            cur_e = max(cur_e, iv.end)
        else:
            total += max(0.0, cur_e - cur_s)
            cur_s, cur_e = iv.start, iv.end
    total += max(0.0, cur_e - cur_s)
    return total


def _overlap_amount(a: TimeInterval, b: TimeInterval) -> float:
    return max(0.0, min(a.end, b.end) - max(a.start, b.start))


def _subtract_other_overlaps(
    targets: list[TimeInterval], others: list[TimeInterval]
) -> list[TimeInterval]:
    """Remove portions overlapping other speakers by > MAX_OTHER_OVERLAP_S.

    Conservative v1: drop the whole target interval when overlap exceeds threshold
    (no partial keep). Never bridges across other speakers.
    """
    kept: list[TimeInterval] = []
    for t in targets:
        bad = False
        for o in others:
            if o.end <= t.start:
                continue
            if o.start >= t.end:
                break
            if _overlap_amount(t, o) > MAX_OTHER_OVERLAP_S:
                bad = True
                break
        if not bad:
            kept.append(t)
    return kept


def _clip_window(iv: TimeInterval) -> TimeInterval | None:
    """Clip to [MIN_EXCERPT_S, MAX_EXCERPT_S]; apply PAD_S only as metadata length.

    Padding into silence is applied at extraction time; here we only size the
    core speech window.
    """
    dur = iv.duration
    if dur < MIN_EXCERPT_S:
        return None
    if dur > MAX_EXCERPT_S:
        # Take the earliest MAX_EXCERPT_S slice (deterministic).
        return TimeInterval(
            start=iv.start, end=iv.start + MAX_EXCERPT_S, segment_index=iv.segment_index
        )
    return iv


def _iou(a: TimeInterval, b: TimeInterval) -> float:
    inter = _overlap_amount(a, b)
    if inter <= 0:
        return 0.0
    union = a.duration + b.duration - inter
    return inter / union if union > 0 else 0.0


def _select_spaced(candidates: list[TimeInterval]) -> list[TimeInterval]:
    """Select up to MAX_EXCERPTS with centre spacing; tie-break longer then earlier."""
    ranked = sorted(
        candidates,
        key=lambda i: (-i.duration, i.start, i.segment_index),
    )
    chosen: list[TimeInterval] = []
    for cand in ranked:
        if len(chosen) >= MAX_EXCERPTS:
            break
        if any(_iou(cand, c) > NEAR_DUPLICATE_IOU for c in chosen):
            continue
        if any(abs(cand.centre - c.centre) < MIN_CENTRE_GAP_S for c in chosen):
            continue
        chosen.append(cand)
    chosen.sort(key=lambda i: (i.start, i.end, i.segment_index))
    return chosen


def select_excerpts_v1(
    segments: Sequence[Mapping[str, Any]],
    *,
    local_speaker_key: str,
    normalize_speaker,
) -> ExcerptSelectionResult:
    """Deterministic excerpt plan for ``quality_policy_id = voice_quality.v1``."""
    assert QUALITY_POLICY_ID == "voice_quality.v1"
    target_raw, other = _parse_speaker_intervals(
        segments,
        local_speaker_key=local_speaker_key,
        normalize_speaker=normalize_speaker,
    )
    merged = _merge_same_speaker(target_raw, other)
    union = _union_duration(merged)
    if union < MIN_TOTAL_UNION_SPEECH_S:
        return ExcerptSelectionResult(
            quality_policy_id=QUALITY_POLICY_ID,
            union_speech_duration_s=union,
            excerpts=(),
            one_excerpt_fallback=False,
            outcome="insufficient_speech",
        )

    cleaned = _subtract_other_overlaps(merged, other)
    windows: list[TimeInterval] = []
    for iv in cleaned:
        clipped = _clip_window(iv)
        if clipped is not None:
            windows.append(clipped)

    if not windows:
        return ExcerptSelectionResult(
            quality_policy_id=QUALITY_POLICY_ID,
            union_speech_duration_s=union,
            excerpts=(),
            one_excerpt_fallback=False,
            outcome="no_eligible_clips",
        )

    selected = _select_spaced(windows)
    one_fallback = False
    if len(selected) == 1 and union >= MIN_TOTAL_UNION_SPEECH_S:
        one_fallback = True

    if not selected:
        # Fallback: single earliest valid window if spacing rejected all but one exists
        selected = windows[:1]
        one_fallback = True

    excerpts = tuple(
        ExcerptPlan(
            start=max(0.0, w.start - PAD_S),
            end=w.end + PAD_S,
            source_segment_indexes=(w.segment_index,),
        )
        for w in selected
    )
    return ExcerptSelectionResult(
        quality_policy_id=QUALITY_POLICY_ID,
        union_speech_duration_s=union,
        excerpts=excerpts,
        one_excerpt_fallback=one_fallback,
        outcome="ok",
    )
