"""Low-confidence span and cluster builders with hardened break rules."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from transcriptx.core.analysis.transcript_quality.words import WordRecord


class SpanBuildConfig:
    """Mutable-friendly config bag for span/cluster construction."""

    def __init__(
        self,
        *,
        low_score_threshold: float = 0.5,
        max_gap_seconds: float = 0.75,
        cluster_merge_seconds: float = 2.0,
        max_spans: int = 50,
        max_clusters: int = 25,
        timestamp_epsilon: float = 1e-6,
    ) -> None:
        self.low_score_threshold = low_score_threshold
        self.max_gap_seconds = max_gap_seconds
        self.cluster_merge_seconds = cluster_merge_seconds
        self.max_spans = max_spans
        self.max_clusters = max_clusters
        self.timestamp_epsilon = timestamp_epsilon


def _coerce_ts(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _valid_playback_range(start: float, end: float) -> bool:
    return end >= start


def _is_low(word: WordRecord, threshold: float) -> bool:
    return word.eligible and word.score is not None and word.score < threshold


def _gap_seconds(prev: WordRecord, curr: WordRecord) -> float:
    assert prev.end is not None and curr.start is not None
    return max(0.0, float(curr.start) - float(prev.end))


def _should_break_span(
    prev: WordRecord,
    curr: WordRecord,
    *,
    cfg: SpanBuildConfig,
) -> bool:
    """Return True if curr must not continue the open low-score span ending at prev."""
    if not _is_low(curr, cfg.low_score_threshold):
        return True
    if (prev.speaker or "") != (curr.speaker or ""):
        return True
    if curr.score is None:
        return True
    if curr.missing_score or curr.invalid_score or curr.out_of_range_score:
        return True
    if curr.start is None or curr.end is None or prev.start is None or prev.end is None:
        return True
    if curr.end < curr.start:
        return True
    if curr.start + cfg.timestamp_epsilon < prev.start:
        return True
    if abs(curr.segment_index - prev.segment_index) > 1:
        return True
    gap = _gap_seconds(prev, curr)
    if curr.segment_index != prev.segment_index and gap > cfg.max_gap_seconds:
        return True
    if gap > cfg.max_gap_seconds:
        return True
    return False


def _preview(words: Sequence[WordRecord], *, limit: int = 12) -> str:
    parts = [w.text for w in words if w.text]
    if len(parts) > limit:
        return " ".join(parts[:limit]) + "…"
    return " ".join(parts)


def _playback_payload(
    start: float, end: float, segment_index: int
) -> Optional[Dict[str, Any]]:
    start_f = _coerce_ts(start)
    end_f = _coerce_ts(end)
    if start_f is None or end_f is None:
        return None
    if not _valid_playback_range(start_f, end_f):
        return None
    return {"start": start_f, "end": end_f, "segment_index": int(segment_index)}


def _span_dict(words: Sequence[WordRecord]) -> Dict[str, Any]:
    assert words
    starts = [w.start for w in words if w.start is not None]
    ends = [w.end for w in words if w.end is not None]
    scores = [float(w.score) for w in words if w.score is not None]
    start = float(min(starts)) if starts else 0.0
    end = float(max(ends)) if ends else start
    mean_score = sum(scores) / len(scores) if scores else None
    segment_index_start = words[0].segment_index
    segment_index_end = words[-1].segment_index
    return {
        "start": start,
        "end": end,
        "speaker": words[0].speaker,
        "mean_score": mean_score,
        "word_count": len(words),
        "text_preview": _preview(words),
        "segment_index_start": segment_index_start,
        "segment_index_end": segment_index_end,
        "word_index_start": words[0].word_index,
        "word_index_end": words[-1].word_index,
        "stream_index_start": words[0].stream_index,
        "stream_index_end": words[-1].stream_index,
        "playback": _playback_payload(start, end, segment_index_start),
    }


def _rank_key(item: Dict[str, Any]) -> tuple:
    mean = item.get("mean_score")
    mean_key = float(mean) if isinstance(mean, (int, float)) else 1.0
    duration = float(item.get("end", 0.0)) - float(item.get("start", 0.0))
    start = float(item.get("start", 0.0))
    return (mean_key, -duration, start)


def _cap(items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    ranked = sorted(items, key=_rank_key)
    return ranked[: max(0, int(limit))]


def build_low_score_spans(
    words: Sequence[WordRecord],
    cfg: SpanBuildConfig,
) -> List[Dict[str, Any]]:
    """Build unbroken low-score spans under hardened continuity rules."""
    spans: List[Dict[str, Any]] = []
    open_words: List[WordRecord] = []

    def _flush() -> None:
        nonlocal open_words
        if open_words:
            spans.append(_span_dict(open_words))
            open_words = []

    for word in words:
        if not _is_low(word, cfg.low_score_threshold):
            _flush()
            continue
        if not open_words:
            open_words = [word]
            continue
        if _should_break_span(open_words[-1], word, cfg=cfg):
            _flush()
            open_words = [word]
        else:
            open_words.append(word)
    _flush()
    return spans


def build_clusters(
    spans: Sequence[Dict[str, Any]],
    cfg: SpanBuildConfig,
) -> List[Dict[str, Any]]:
    """Merge adjacent same-speaker spans within ``cluster_merge_seconds``."""
    if not spans:
        return []
    ordered = sorted(
        spans,
        key=lambda s: (float(s.get("start", 0.0)), float(s.get("end", 0.0))),
    )
    clusters: List[Dict[str, Any]] = []
    current: List[Dict[str, Any]] = [ordered[0]]

    def _flush_cluster() -> None:
        nonlocal current
        if not current:
            return
        start = float(current[0]["start"])
        end = float(current[-1]["end"])
        scores = [
            float(s["mean_score"])
            for s in current
            if isinstance(s.get("mean_score"), (int, float))
        ]
        word_count = sum(int(s.get("word_count") or 0) for s in current)
        previews = [str(s.get("text_preview") or "") for s in current if s.get("text_preview")]
        clusters.append(
            {
                "start": start,
                "end": end,
                "speaker": current[0].get("speaker"),
                "mean_score": (sum(scores) / len(scores)) if scores else None,
                "word_count": word_count,
                "span_count": len(current),
                "text_preview": " … ".join(previews)[:240],
                "segment_index_start": current[0].get("segment_index_start"),
                "segment_index_end": current[-1].get("segment_index_end"),
                "word_index_start": current[0].get("word_index_start"),
                "word_index_end": current[-1].get("word_index_end"),
                "playback": _playback_payload(
                    start, end, int(current[0].get("segment_index_start") or 0)
                ),
            }
        )
        current = []

    for span in ordered[1:]:
        prev = current[-1]
        same_speaker = (prev.get("speaker") or "") == (span.get("speaker") or "")
        gap = float(span.get("start", 0.0)) - float(prev.get("end", 0.0))
        if same_speaker and gap <= cfg.cluster_merge_seconds:
            current.append(span)
        else:
            _flush_cluster()
            current = [span]
    _flush_cluster()
    return clusters


def build_spans_and_clusters(
    words: Sequence[WordRecord],
    cfg: SpanBuildConfig,
) -> Dict[str, Any]:
    """Return all spans/clusters plus capped emitted lists and counts."""
    all_spans = build_low_score_spans(words, cfg)
    all_clusters = build_clusters(all_spans, cfg)
    emitted_spans = _cap(all_spans, cfg.max_spans)
    emitted_clusters = _cap(all_clusters, cfg.max_clusters)
    return {
        "spans_total_count": len(all_spans),
        "spans_emitted_count": len(emitted_spans),
        "clusters_total_count": len(all_clusters),
        "clusters_emitted_count": len(emitted_clusters),
        "spans": emitted_spans,
        "clusters": emitted_clusters,
    }
