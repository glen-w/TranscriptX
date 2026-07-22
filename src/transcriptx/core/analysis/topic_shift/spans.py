"""Span IDs, coverage spans, and boundary→segment mapping."""

from __future__ import annotations

import hashlib
import json
from typing import Sequence

from transcriptx.core.analysis.topic_shift.detector import PeakCandidate
from transcriptx.core.analysis.topic_shift.segments import CanonicalTopicSegment
from transcriptx.core.analysis.topic_shift.semantics import SCHEMA_VERSION
from transcriptx.core.analysis.topic_shift.windowing import TopicWindow
from transcriptx.core.models.events import Event, generate_event_id
from transcriptx.core.utils.canonicalization import compute_transcript_identity_hash


def format_hhmm(seconds: float) -> str:
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def make_span_id(
    *,
    transcript_identity: str,
    segment_start_idx: int,
    segment_end_idx: int,
    semantics_version: str,
) -> str:
    payload = {
        "transcript_identity": transcript_identity,
        "segment_start_idx": int(segment_start_idx),
        "segment_end_idx": int(segment_end_idx),
        "semantics_version": semantics_version,
        "schema_version": SCHEMA_VERSION,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"ts_span_{hashlib.sha256(blob.encode('utf-8')).hexdigest()[:24]}"


def nearest_renderable_source_index(
    preferred: int,
    *,
    renderable: Sequence[int],
) -> int | None:
    if not renderable:
        return None
    if preferred in renderable:
        return preferred
    return min(renderable, key=lambda idx: (abs(idx - preferred), idx))


def map_peak_to_boundary(
    peak: PeakCandidate,
    windows: Sequence[TopicWindow],
    segments: Sequence[CanonicalTopicSegment],
) -> tuple[int, float, int] | None:
    """
    Map peak at distance index i to inter-segment boundary at start of window i+1.

    Returns (source_index, time, canonical_position) for the right-hand span start.
    """
    i = peak.distance_index
    if i + 1 >= len(windows):
        return None
    right = windows[i + 1]
    if not right.segment_indexes:
        return None
    source_index = int(right.segment_indexes[0])
    # Prefer canonical segment matching source_index
    match = next((s for s in segments if s.source_index == source_index), None)
    if match is None:
        return None
    return source_index, float(match.start), int(match.canonical_position)


def build_coverage_and_events(
    *,
    segments: Sequence[CanonicalTopicSegment],
    windows: Sequence[TopicWindow],
    accepted_peaks: Sequence[PeakCandidate],
    transcript_identity: str,
    semantics_version: str,
    backend: str,
    analytical_status: str,
    keyword_hints_by_span: Sequence[Sequence[str]] | None = None,
) -> tuple[list[dict], list[Event], list[dict]]:
    """
    Build coverage spans + Event boundaries.

    Post-snap: dedupe coincident source indices, order by time.
    """
    renderable = [s.source_index for s in segments]
    # Snap peaks → unique boundaries by source_index
    boundaries: list[tuple[int, float, int, PeakCandidate]] = []
    for peak in accepted_peaks:
        mapped = map_peak_to_boundary(peak, windows, segments)
        if mapped is None:
            continue
        source_index, time, canon_pos = mapped
        boundaries.append((source_index, time, canon_pos, peak))

    # Dedupe coincident source_index: keep higher prominence
    by_src: dict[int, tuple[int, float, int, PeakCandidate]] = {}
    for row in boundaries:
        prev = by_src.get(row[0])
        if prev is None or row[3].local_prominence > prev[3].local_prominence:
            by_src[row[0]] = row
    boundaries = sorted(by_src.values(), key=lambda r: (r[1], r[0]))

    events: list[Event] = []
    event_meta: list[dict] = []
    for source_index, time, _canon, peak in boundaries:
        eid = generate_event_id(
            transcript_identity,
            "topic_shift",
            source_index,
            source_index,
            time,
            time,
        )
        evidence = [
            {
                "raw_distance": peak.raw_distance,
                "local_prominence": peak.local_prominence,
                "decision_threshold": peak.decision_threshold,
                "normalized_strength": peak.normalized_strength,
                "backend": backend,
                "boundary_window_index": peak.distance_index,
                "semantics_version": semantics_version,
            }
        ]
        links = [
            {
                "type": "segment_jump",
                "source_index": source_index,
                "time": time,
            }
        ]
        events.append(
            Event(
                event_id=eid,
                kind="topic_shift",
                time_start=time,
                time_end=time,
                speaker=None,
                segment_start_idx=source_index,
                segment_end_idx=source_index,
                severity=float(peak.normalized_strength),
                score=float(peak.normalized_strength),
                evidence=evidence,
                links=links,
            )
        )
        event_meta.append({"event_id": eid, "source_index": source_index, "peak": peak})

    # Split segments into spans at boundary source indices
    if not segments:
        return [], [], []

    split_sources = [m["source_index"] for m in event_meta]
    # Build ranges over canonical order
    ordered = list(segments)
    cut_positions = []
    for src in split_sources:
        for seg in ordered:
            if seg.source_index == src:
                cut_positions.append(seg.canonical_position)
                break
    cut_positions = sorted(set(cut_positions))

    ranges: list[tuple[int, int]] = []  # inclusive canonical positions
    start_pos = 0
    last_pos = ordered[-1].canonical_position
    for cut in cut_positions:
        if cut <= start_pos:
            continue
        ranges.append((start_pos, cut - 1))
        start_pos = cut
    ranges.append((start_pos, last_pos))

    # Map event by starting source
    event_by_start_src = {m["source_index"]: m["event_id"] for m in event_meta}

    spans: list[dict] = []
    for idx, (c0, c1) in enumerate(ranges):
        segs = [s for s in ordered if c0 <= s.canonical_position <= c1]
        if not segs:
            continue
        seg_start = segs[0].source_index
        seg_end = segs[-1].source_index
        t0 = segs[0].start
        t1 = segs[-1].end
        leading = event_by_start_src.get(seg_start) if idx > 0 else None
        # For idx>0, leading boundary is the event at this span's start
        if idx > 0:
            leading = event_by_start_src.get(seg_start)
        viewer_target = nearest_renderable_source_index(seg_start, renderable=renderable)
        if viewer_target is None:
            viewer_target = seg_start
        label = f"Segment {idx + 1} · {format_hhmm(t0)}–{format_hhmm(t1)}"
        hints: list[str] = []
        if keyword_hints_by_span and idx < len(keyword_hints_by_span):
            hints = list(keyword_hints_by_span[idx])
        if analytical_status == "no_shift_detected":
            boundary_status = "no_shift_detected"
            inferred = False
            leading = None
        elif analytical_status == "success":
            boundary_status = "inferred"
            inferred = True
            if idx == 0:
                leading = None
        else:
            boundary_status = "abstained"
            inferred = False
            leading = None

        spans.append(
            {
                "span_id": make_span_id(
                    transcript_identity=transcript_identity,
                    segment_start_idx=seg_start,
                    segment_end_idx=seg_end,
                    semantics_version=semantics_version,
                ),
                "index": idx,
                "time_start": float(t0),
                "time_end": float(t1),
                "segment_start_idx": int(seg_start),
                "segment_end_idx": int(seg_end),
                "label": label,
                "keyword_hints": hints,
                "inferred": inferred,
                "boundary_status": boundary_status,
                "leading_boundary_id": leading if idx > 0 else None,
                "viewer_target_source_index": int(viewer_target),
                "analytical_status": analytical_status,
                "backend": backend,
                "semantics_version": semantics_version,
                "provenance": {
                    "schema_version": SCHEMA_VERSION,
                    "backend": backend,
                },
            }
        )

    return spans, events, event_meta


def transcript_identity_for_segments(raw_segments: Sequence[dict]) -> str:
    return compute_transcript_identity_hash(raw_segments)
