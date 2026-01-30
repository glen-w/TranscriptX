"""Core highlight computation (pure logic, no I/O)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional
import math

from transcriptx.utils.text_utils import is_named_speaker, count_words
from transcriptx.core.utils.nlp_utils import ALL_STOPWORDS, ALL_VERBAL_TICS
from transcriptx.core.analysis.exemplars import (
    SegmentRecord,
    SpeakerExemplarsConfig,
    _compute_unique_scores,
    _compute_tfidf_scores,
    _rank_normalize,
    _percentile,
    _normalize_text,
    _tokenize,
)


@dataclass(frozen=True)
class SegmentLite:
    segment_key: str
    segment_db_id: Optional[int]
    segment_uuid: Optional[str]
    segment_index: int
    speaker_display: str
    speaker_id: Optional[object]
    start: float
    end: float
    text: str
    sentiment_compound: Optional[float] = None
    emotion_dist: Optional[Dict[str, float]] = None
    context_emotion: Optional[str] = None


@dataclass(frozen=True)
class QuoteCandidate:
    segment_keys: List[str]
    segment_db_ids: List[int]
    segment_uuids: List[str]
    segment_indexes: List[int]
    speaker_display: str
    speaker_id: Optional[object]
    start: float
    end: float
    text: str
    word_count: int
    sentiment_compound: Optional[float] = None
    emotion_dist: Optional[Dict[str, float]] = None
    context_emotion: Optional[str] = None


def _minmax_normalize(values: List[float]) -> List[float]:
    if not values:
        return []
    vmin = min(values)
    vmax = max(values)
    if math.isclose(vmin, vmax):
        return [0.0 for _ in values]
    return [(v - vmin) / (vmax - vmin) for v in values]


def _normalize_scores(records: List[SegmentRecord], raw_scores: List[float]) -> List[float]:
    ranked = _rank_normalize(records, raw_scores)
    if ranked is not None:
        return ranked
    return _minmax_normalize(raw_scores)


def _aggregate_emotion_dist(
    dists: List[Optional[Dict[str, float]]],
) -> Optional[Dict[str, float]]:
    merged: Dict[str, float] = {}
    count = 0
    for dist in dists:
        if not dist:
            continue
        count += 1
        for key, value in dist.items():
            merged[key] = merged.get(key, 0.0) + float(value)
    if not merged or count == 0:
        return None
    return {key: value / count for key, value in merged.items()}


def _merge_adjacent_segments(
    segments: List[SegmentLite],
    enabled: bool,
    max_gap_seconds: float,
    max_segments: int,
    max_words: int,
) -> List[QuoteCandidate]:
    if not segments:
        return []
    if not enabled:
        return [
            QuoteCandidate(
                segment_keys=[seg.segment_key],
                segment_db_ids=[seg.segment_db_id] if seg.segment_db_id else [],
                segment_uuids=[seg.segment_uuid] if seg.segment_uuid else [],
                segment_indexes=[seg.segment_index],
                speaker_display=seg.speaker_display,
                speaker_id=seg.speaker_id,
                start=seg.start,
                end=seg.end,
                text=seg.text.strip(),
                word_count=count_words(seg.text),
                sentiment_compound=seg.sentiment_compound,
                emotion_dist=seg.emotion_dist,
                context_emotion=seg.context_emotion,
            )
            for seg in segments
            if seg.text.strip()
        ]

    merged: List[QuoteCandidate] = []
    current = segments[0]
    current_text = current.text.strip()
    current_words = count_words(current_text)
    current_keys = [current.segment_key]
    current_db_ids = [current.segment_db_id] if current.segment_db_id else []
    current_uuids = [current.segment_uuid] if current.segment_uuid else []
    current_indexes = [current.segment_index]
    current_sentiments = [current.sentiment_compound]
    current_emotions = [current.emotion_dist]
    current_context = [current.context_emotion]
    current_start = current.start
    current_end = current.end
    current_speaker = current.speaker_display
    current_speaker_id = current.speaker_id
    segment_count = 1

    def _flush() -> None:
        nonlocal merged, current_text, current_words
        merged.append(
            QuoteCandidate(
                segment_keys=list(current_keys),
                segment_db_ids=list(current_db_ids),
                segment_uuids=list(current_uuids),
                segment_indexes=list(current_indexes),
                speaker_display=current_speaker,
                speaker_id=current_speaker_id,
                start=current_start,
                end=current_end,
                text=current_text,
                word_count=current_words,
                sentiment_compound=(
                    sum([v for v in current_sentiments if v is not None])
                    / max(1, len([v for v in current_sentiments if v is not None]))
                    if any(v is not None for v in current_sentiments)
                    else None
                ),
                emotion_dist=_aggregate_emotion_dist(current_emotions),
                context_emotion=next(
                    (v for v in current_context if v), None
                ),
            )
        )

    for seg in segments[1:]:
        gap = seg.start - current_end
        can_merge = (
            seg.speaker_display == current_speaker
            and gap <= max_gap_seconds
            and segment_count < max_segments
        )
        if can_merge:
            next_text = seg.text.strip()
            next_words = count_words(next_text)
            if current_words + next_words <= max_words:
                current_text = f"{current_text} {next_text}".strip()
                current_words += next_words
                current_end = seg.end
                current_keys.append(seg.segment_key)
                if seg.segment_db_id:
                    current_db_ids.append(seg.segment_db_id)
                if seg.segment_uuid:
                    current_uuids.append(seg.segment_uuid)
                current_indexes.append(seg.segment_index)
                current_sentiments.append(seg.sentiment_compound)
                current_emotions.append(seg.emotion_dist)
                current_context.append(seg.context_emotion)
                segment_count += 1
                continue

        _flush()
        current = seg
        current_text = seg.text.strip()
        current_words = count_words(current_text)
        current_keys = [seg.segment_key]
        current_db_ids = [seg.segment_db_id] if seg.segment_db_id else []
        current_uuids = [seg.segment_uuid] if seg.segment_uuid else []
        current_indexes = [seg.segment_index]
        current_sentiments = [seg.sentiment_compound]
        current_emotions = [seg.emotion_dist]
        current_context = [seg.context_emotion]
        current_start = seg.start
        current_end = seg.end
        current_speaker = seg.speaker_display
        current_speaker_id = seg.speaker_id
        segment_count = 1

    _flush()
    return merged


def _build_segment_records(candidates: List[QuoteCandidate]) -> List[SegmentRecord]:
    records: List[SegmentRecord] = []
    for candidate in candidates:
        records.append(
            SegmentRecord(
                segment_id=candidate.segment_keys[0],
                segment_index=candidate.segment_indexes[0],
                speaker_id=candidate.speaker_display,
                text=candidate.text,
                word_count=candidate.word_count,
                start_time=candidate.start,
                end_time=candidate.end,
            )
        )
    return records


def _intensity_score(candidate: QuoteCandidate) -> float:
    compound = candidate.sentiment_compound or 0.0
    valence_abs = abs(compound)
    emotion_neg = 0.0
    if candidate.emotion_dist:
        for key in ["anger", "fear", "disgust", "sadness", "negative"]:
            emotion_neg += float(candidate.emotion_dist.get(key, 0.0))
    if candidate.context_emotion:
        label = candidate.context_emotion.lower()
        if label in {"anger", "fear", "sadness", "disgust"}:
            emotion_neg = max(emotion_neg, 0.6)
    return max(valence_abs, emotion_neg)


def _conflict_marker_score(text: str) -> float:
    lowered = text.lower()
    markers = [
        "but",
        "however",
        "no",
        "actually",
        "wait",
        "that's not",
        "that is not",
        "i disagree",
        "we can't",
        "we cannot",
        "can't",
        "won't",
    ]
    score = 0.0
    for marker in markers:
        if marker in lowered:
            score += 0.15
    return min(score, 1.0)


def _conflict_score(candidate: QuoteCandidate) -> float:
    compound = candidate.sentiment_compound or 0.0
    negativity = max(0.0, -compound)
    marker_score = _conflict_marker_score(candidate.text)
    return min(1.0, negativity + marker_score)


def _keyword_richness_scores(texts: List[str]) -> List[float]:
    if not texts:
        return []
    return _compute_tfidf_scores(texts, max_features=1000, ngram_range=(1, 2))


def _select_with_constraints(
    candidates: List[QuoteCandidate],
    scores: List[float],
    min_gap_seconds: float,
    max_consecutive_per_speaker: int,
    max_items: int,
) -> List[int]:
    if not candidates:
        return []
    ranked = list(range(len(candidates)))
    ranked.sort(
        key=lambda idx: (
            -scores[idx],
            candidates[idx].segment_indexes[0],
            candidates[idx].segment_keys[0],
        )
    )
    selected: List[int] = []
    last_speaker = None
    consecutive_count = 0
    for idx in ranked:
        if len(selected) >= max_items:
            break
        candidate = candidates[idx]
        too_close = False
        for sel_idx in selected:
            if abs(candidate.start - candidates[sel_idx].start) < min_gap_seconds:
                too_close = True
                break
        if too_close:
            continue
        if candidate.speaker_display == last_speaker:
            if consecutive_count >= max_consecutive_per_speaker:
                continue
            consecutive_count += 1
        else:
            last_speaker = candidate.speaker_display
            consecutive_count = 1
        selected.append(idx)
    return selected


def _build_quote_payload(
    candidate: QuoteCandidate,
    total_score: float,
    breakdown: Dict[str, Any],
    reasons: List[str],
) -> Dict[str, Any]:
    return {
        "id": None,
        "speaker": candidate.speaker_display,
        "start": candidate.start,
        "end": candidate.end,
        "segment_refs": {
            "segment_db_ids": candidate.segment_db_ids,
            "segment_uuids": candidate.segment_uuids,
            "segment_indexes": candidate.segment_indexes,
        },
        "quote": candidate.text,
        "score": {
            "total": round(total_score, 6),
            "breakdown": breakdown,
        },
        "reasons": reasons,
    }


def _format_segment_key(segment: SegmentLite) -> str:
    if segment.segment_db_id is not None:
        return f"db:{segment.segment_db_id}"
    if segment.segment_uuid:
        return f"uuid:{segment.segment_uuid}"
    return segment.segment_key


def _assign_quote_ids(quotes: List[Dict[str, Any]], candidates: List[QuoteCandidate]) -> None:
    for quote, candidate in zip(quotes, candidates):
        anchor_key = _format_segment_key(
            SegmentLite(
                segment_key=candidate.segment_keys[0],
                segment_db_id=candidate.segment_db_ids[0]
                if candidate.segment_db_ids
                else None,
                segment_uuid=candidate.segment_uuids[0]
                if candidate.segment_uuids
                else None,
                segment_index=candidate.segment_indexes[0],
                speaker_display=candidate.speaker_display,
                speaker_id=candidate.speaker_id,
                start=candidate.start,
                end=candidate.end,
                text=candidate.text,
            )
        )
        normalized = _normalize_text(candidate.text)
        quote["id"] = f"{anchor_key}|{normalized}"


def compute_highlights(segments: List[SegmentLite], cfg: Any) -> Dict[str, Any]:
    named_segments = [
        seg
        for seg in segments
        if seg.text.strip() and is_named_speaker(seg.speaker_display)
    ]
    named_segments.sort(key=lambda seg: seg.segment_index)

    window_start = named_segments[0].start if named_segments else 0.0
    window_policy = getattr(cfg.cold_open, "window_policy", "seconds")
    window_seconds = float(getattr(cfg.cold_open, "window_seconds", 90.0))
    if window_policy == "segments":
        cutoff = min(len(named_segments), cfg.counts.cold_open_quotes)
        window_end = named_segments[cutoff - 1].end if cutoff else window_start
    else:
        window_end = window_start + window_seconds

    candidates = _merge_adjacent_segments(
        named_segments,
        enabled=cfg.merge_adjacent.enabled,
        max_gap_seconds=float(cfg.merge_adjacent.max_gap_seconds),
        max_segments=int(cfg.merge_adjacent.max_segments),
        max_words=int(cfg.thresholds.max_quote_words),
    )

    filtered_candidates = []
    for candidate in candidates:
        if candidate.word_count < cfg.thresholds.min_quote_words:
            continue
        if candidate.word_count > cfg.thresholds.max_quote_words:
            continue
        filtered_candidates.append(candidate)
    candidates = filtered_candidates

    records = _build_segment_records(candidates)

    intensity_raw = [_intensity_score(c) for c in candidates]
    conflict_raw = [_conflict_score(c) for c in candidates]
    uniqueness_raw = _compute_unique_scores(records, SpeakerExemplarsConfig())
    keyword_raw = _keyword_richness_scores([c.text for c in candidates])

    intensity_norm = _normalize_scores(records, intensity_raw)
    conflict_norm = _normalize_scores(records, conflict_raw)
    uniqueness_norm = _normalize_scores(records, uniqueness_raw)
    keyword_norm = _normalize_scores(records, keyword_raw)

    weights = {
        "intensity": cfg.weights.intensity,
        "conflict": cfg.weights.conflict,
        "uniqueness": cfg.weights.uniqueness,
        "keyword_richness": cfg.weights.keyword_richness,
    }
    weight_sum = sum(weights.values()) or 1.0

    combined_scores = []
    for idx in range(len(candidates)):
        combined = (
            intensity_norm[idx] * weights["intensity"]
            + conflict_norm[idx] * weights["conflict"]
            + uniqueness_norm[idx] * weights["uniqueness"]
            + keyword_norm[idx] * weights["keyword_richness"]
        ) / weight_sum
        combined_scores.append(combined)

    selected_indexes = _select_with_constraints(
        candidates=candidates,
        scores=combined_scores,
        min_gap_seconds=float(cfg.thresholds.min_gap_seconds),
        max_consecutive_per_speaker=int(cfg.thresholds.max_consecutive_per_speaker),
        max_items=int(cfg.counts.total_highlights),
    )

    quotes = []
    for idx in selected_indexes:
        breakdown = {
            "intensity": {
                "raw": intensity_raw[idx],
                "normalized": intensity_norm[idx],
            },
            "conflict": {"raw": conflict_raw[idx], "normalized": conflict_norm[idx]},
            "uniqueness": {
                "raw": uniqueness_raw[idx],
                "normalized": uniqueness_norm[idx],
            },
            "keyword_richness": {
                "raw": keyword_raw[idx] if idx < len(keyword_raw) else 0.0,
                "normalized": keyword_norm[idx] if idx < len(keyword_norm) else 0.0,
            },
        }
        reasons = []
        if intensity_norm[idx] >= 0.6:
            reasons.append("high intensity")
        if conflict_norm[idx] >= 0.6:
            reasons.append("conflict signals")
        if uniqueness_norm[idx] >= 0.6:
            reasons.append("distinctive phrasing")
        if keyword_norm[idx] >= 0.6:
            reasons.append("keyword richness")
        quote = _build_quote_payload(
            candidates[idx], combined_scores[idx], breakdown, reasons
        )
        quotes.append(quote)
    _assign_quote_ids(quotes, [candidates[idx] for idx in selected_indexes])

    cold_open_payload = []
    if cfg.sections.cold_open_enabled:
        cold_open_candidates = [
            (idx, candidates[idx])
            for idx in selected_indexes
            if candidates[idx].start <= window_end
        ]
        cold_open_candidates.sort(
            key=lambda item: (-combined_scores[item[0]], item[1].segment_indexes[0])
        )
        cold_open = cold_open_candidates[: cfg.counts.cold_open_quotes]
        if cold_open:
            cold_open_payload = [
                _build_quote_payload(
                    candidate,
                    combined_scores[idx],
                    {
                        "intensity": {
                            "raw": intensity_raw[idx],
                            "normalized": intensity_norm[idx],
                        }
                    },
                    ["cold open"],
                )
                for idx, candidate in cold_open
            ]
            _assign_quote_ids(
                cold_open_payload, [candidate for _, candidate in cold_open]
            )

    conflict_events = []
    conflict_rows = []
    if cfg.sections.conflict_points_enabled:
        conflict_events, conflict_rows = _compute_conflict_events(
            named_segments,
            candidates,
            combined_scores,
            cfg,
        )

    phrases = []
    if cfg.sections.emblematic_phrases_enabled:
        phrases = _compute_emblematic_phrases(named_segments, cfg)

    return {
        "schema_version": 1,
        "schema_id": "transcriptx.highlights.v1",
        "schema_url": None,
        "scope": "global",
        "sections": {
            "cold_open": {
                "window": {"start": window_start, "end": window_end},
                "window_policy": window_policy,
                "first_named_segment_index": named_segments[0].segment_index
                if named_segments
                else None,
                "items": cold_open_payload,
            },
            "conflict_points": {
                "window_params": {
                    "window_seconds": cfg.conflict.window_seconds,
                    "step_seconds": cfg.conflict.step_seconds,
                    "percentile_threshold": cfg.thresholds.conflict_spike_percentile,
                    "merge_gap_seconds": cfg.conflict.merge_gap_seconds,
                },
                "events": conflict_events,
            },
            "emblematic_phrases": {"phrases": phrases},
        },
        "metadata": {
            "input_segments": len(segments),
            "named_segments": len(named_segments),
        },
        "conflict_rows": conflict_rows,
    }


def _compute_conflict_events(
    segments: List[SegmentLite],
    candidates: List[QuoteCandidate],
    candidate_scores: List[float],
    cfg: Any,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not segments:
        return [], []
    window_seconds = float(cfg.conflict.window_seconds)
    step_seconds = float(cfg.conflict.step_seconds)
    start = segments[0].start
    end = segments[-1].end
    windows: List[Dict[str, Any]] = []
    cursor = start
    while cursor <= end:
        window_end = cursor + window_seconds
        window_segments = [
            seg for seg in segments if seg.start >= cursor and seg.start <= window_end
        ]
        if window_segments:
            conflict_raw = [_conflict_score(QuoteCandidate(
                segment_keys=[seg.segment_key],
                segment_db_ids=[seg.segment_db_id] if seg.segment_db_id else [],
                segment_uuids=[seg.segment_uuid] if seg.segment_uuid else [],
                segment_indexes=[seg.segment_index],
                speaker_display=seg.speaker_display,
                speaker_id=seg.speaker_id,
                start=seg.start,
                end=seg.end,
                text=seg.text,
                word_count=count_words(seg.text),
                sentiment_compound=seg.sentiment_compound,
                emotion_dist=seg.emotion_dist,
                context_emotion=seg.context_emotion,
            )) for seg in window_segments]
            avg_conflict = sum(conflict_raw) / len(conflict_raw)
            turn_taking = _turn_taking_rate(window_segments)
            window_spike = avg_conflict + 0.2 * turn_taking
            windows.append(
                {
                    "start": cursor,
                    "end": window_end,
                    "window_spike_raw": window_spike,
                    "conflict_content_raw": avg_conflict,
                    "turn_taking": turn_taking,
                    "participants": _participants(window_segments),
                }
            )
        cursor += step_seconds

    if not windows:
        return [], []

    spike_values = [w["window_spike_raw"] for w in windows]
    threshold = _percentile(spike_values, cfg.thresholds.conflict_spike_percentile)
    selected = [w for w in windows if w["window_spike_raw"] >= threshold]
    merged = _merge_windows(selected, cfg.conflict.merge_gap_seconds)

    mean = sum(spike_values) / len(spike_values)
    std = math.sqrt(
        sum((v - mean) ** 2 for v in spike_values) / max(1, len(spike_values))
    )
    events = []
    rows = []
    merged.sort(key=lambda w: -w["window_spike_raw"])
    merged = merged[: cfg.counts.conflict_windows]
    for idx, window in enumerate(merged):
        anchor = _select_anchor_quote(window, candidates, candidate_scores)
        event_id = f"conflict-{idx+1}"
        z_like = (window["window_spike_raw"] - mean) / std if std else 0.0
        participants = window["participants"]
        participant_ids = [p.get("speaker_id") for p in participants]
        participant_displays = [p.get("speaker_display") for p in participants]
        event = {
            "event_id": event_id,
            "start": window["start"],
            "end": window["end"],
            "peak_time": window["peak_time"],
            "peak_score": window["window_spike_raw"],
            "participants": participants,
            "anchor_quote": anchor,
            "score_breakdown": {
                "window_spike_score": {
                    "raw_window_score": window["window_spike_raw"],
                    "threshold": threshold,
                    "percentile": cfg.thresholds.conflict_spike_percentile,
                    "z_like": z_like,
                },
                "conflict_content_score": {
                    "negativity": window["conflict_content_raw"],
                    "turn_taking": window["turn_taking"],
                    "lexical_markers": window["conflict_content_raw"],
                },
            },
        }
        events.append(event)
        rows.append(
            {
                "event_id": event_id,
                "start_s": window["start"],
                "end_s": window["end"],
                "peak_s": window["peak_time"],
                "peak_score": window["window_spike_raw"],
                "participant_ids": ";".join(
                    [str(pid) for pid in participant_ids if pid is not None]
                ),
                "participant_displays": ";".join(
                    [p for p in participant_displays if p]
                ),
                "anchor_speaker": anchor.get("speaker") if anchor else "",
                "anchor_start_s": anchor.get("start") if anchor else None,
                "anchor_end_s": anchor.get("end") if anchor else None,
                "anchor_quote": anchor.get("quote") if anchor else "",
                "breakdown_window_spike_raw": window["window_spike_raw"],
                "breakdown_window_spike_percentile": cfg.thresholds.conflict_spike_percentile,
                "breakdown_conflict_negativity": window["conflict_content_raw"],
                "breakdown_conflict_turn_taking": window["turn_taking"],
                "breakdown_conflict_markers": window["conflict_content_raw"],
            }
        )
    return events, rows


def _turn_taking_rate(segments: List[SegmentLite]) -> float:
    if len(segments) < 2:
        return 0.0
    switches = 0
    prev = segments[0].speaker_display
    for seg in segments[1:]:
        if seg.speaker_display != prev:
            switches += 1
        prev = seg.speaker_display
    return switches / max(1, len(segments) - 1)


def _participants(segments: List[SegmentLite]) -> List[Dict[str, Any]]:
    seen = {}
    for seg in segments:
        if not is_named_speaker(seg.speaker_display):
            continue
        if seg.speaker_display not in seen:
            seen[seg.speaker_display] = seg.speaker_id
    return [
        {"speaker_id": speaker_id, "speaker_display": speaker_display}
        for speaker_display, speaker_id in seen.items()
    ]


def _merge_windows(windows: List[Dict[str, Any]], max_gap: float) -> List[Dict[str, Any]]:
    if not windows:
        return []
    windows.sort(key=lambda w: w["start"])
    merged = [windows[0]]
    for window in windows[1:]:
        last = merged[-1]
        overlap = set([p["speaker_display"] for p in last["participants"]]) & set(
            [p["speaker_display"] for p in window["participants"]]
        )
        if window["start"] - last["end"] <= max_gap and overlap:
            last["end"] = max(last["end"], window["end"])
            if window["window_spike_raw"] > last.get("window_spike_raw", 0.0):
                last["window_spike_raw"] = window["window_spike_raw"]
                last["peak_time"] = window["start"]
            last["participants"] = _merge_participants(
                last["participants"], window["participants"]
            )
        else:
            merged.append(window)
    for window in merged:
        if "peak_time" not in window:
            window["peak_time"] = window["start"]
    return merged


def _merge_participants(
    left: List[Dict[str, Any]], right: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    merged: Dict[str, Any] = {}
    for entry in left + right:
        name = entry.get("speaker_display")
        if not name:
            continue
        merged[name] = entry.get("speaker_id")
    return [
        {"speaker_display": name, "speaker_id": speaker_id}
        for name, speaker_id in merged.items()
    ]


def _select_anchor_quote(
    window: Dict[str, Any],
    candidates: List[QuoteCandidate],
    candidate_scores: List[float],
) -> Dict[str, Any]:
    if not candidates:
        return {}
    in_window = [
        (idx, cand)
        for idx, cand in enumerate(candidates)
        if cand.start >= window["start"] and cand.start <= window["end"]
    ]
    if not in_window:
        return {}
    in_window.sort(
        key=lambda item: (
            -candidate_scores[item[0]],
            item[1].segment_indexes[0],
        )
    )
    idx, cand = in_window[0]
    return {
        "id": None,
        "speaker": cand.speaker_display,
        "start": cand.start,
        "end": cand.end,
        "segment_refs": {
            "segment_db_ids": cand.segment_db_ids,
            "segment_uuids": cand.segment_uuids,
            "segment_indexes": cand.segment_indexes,
        },
        "quote": cand.text,
        "score": {"total": candidate_scores[idx]},
        "reasons": ["anchor quote"],
    }


def _compute_emblematic_phrases(
    segments: List[SegmentLite], cfg: Any
) -> List[Dict[str, Any]]:
    min_len = cfg.thresholds.min_phrase_len
    max_len = cfg.thresholds.max_phrase_len
    min_freq = cfg.thresholds.min_phrase_frequency

    docs = [seg.text.lower() for seg in segments if seg.text.strip()]
    vectorizer_scores = _compute_tfidf_scores(docs, max_features=1000, ngram_range=(1, 2))

    phrase_stats: Dict[str, Dict[str, Any]] = {}
    for idx, seg in enumerate(segments):
        tokens = [t for t in _tokenize(seg.text)]
        if not tokens:
            continue
        for n in range(min_len, max_len + 1):
            for i in range(len(tokens) - n + 1):
                phrase_tokens = tokens[i : i + n]
                if all(
                    token in ALL_STOPWORDS or token in ALL_VERBAL_TICS
                    for token in phrase_tokens
                ):
                    continue
                phrase = " ".join(phrase_tokens)
                stats = phrase_stats.setdefault(
                    phrase,
                    {
                        "tokens": phrase_tokens,
                        "count": 0,
                        "speakers": set(),
                        "first_seen": seg.start,
                        "last_seen": seg.end,
                        "examples": [],
                        "tfidf_scores": [],
                    },
                )
                stats["count"] += 1
                stats["speakers"].add(seg.speaker_display)
                stats["first_seen"] = min(stats["first_seen"], seg.start)
                stats["last_seen"] = max(stats["last_seen"], seg.end)
                stats["examples"].append((seg.segment_index, seg))
                if idx < len(vectorizer_scores):
                    stats["tfidf_scores"].append(vectorizer_scores[idx])

    phrases = []
    max_speakers = max((len(v["speakers"]) for v in phrase_stats.values()), default=1)
    for phrase, stats in phrase_stats.items():
        if stats["count"] < min_freq:
            continue
        frequency_score = math.log(1 + stats["count"])
        dispersion_score = len(stats["speakers"]) / max_speakers
        distinctiveness = (
            sum(stats["tfidf_scores"]) / len(stats["tfidf_scores"])
            if stats["tfidf_scores"]
            else 0.0
        )
        total = frequency_score + dispersion_score + distinctiveness
        phrases.append(
            {
                "phrase": phrase,
                "tokens": stats["tokens"],
                "count_total": stats["count"],
                "count_speakers": len(stats["speakers"]),
                "first_seen": stats["first_seen"],
                "last_seen": stats["last_seen"],
                "examples": _select_phrase_examples(stats["examples"]),
                "score": {
                    "total": total,
                    "breakdown": {
                        "frequency": frequency_score,
                        "dispersion": dispersion_score,
                        "distinctiveness": distinctiveness,
                    },
                },
            }
        )

    phrases.sort(
        key=lambda p: (-p["score"]["total"], -len(p["phrase"]), p["first_seen"], p["phrase"])
    )
    phrases = _dedupe_phrases(phrases)
    return phrases[: cfg.counts.emblematic_phrases]


def _select_phrase_examples(examples: List[tuple[int, SegmentLite]]) -> List[Dict[str, Any]]:
    if not examples:
        return []
    sorted_examples = sorted(examples, key=lambda item: item[0])
    earliest = sorted_examples[0][1]
    latest = sorted_examples[-1][1]
    best = sorted_examples[0][1]
    selected = [earliest, latest, best]
    unique = []
    seen = set()
    for seg in selected:
        key = seg.segment_key
        if key in seen:
            continue
        seen.add(key)
        unique.append(
            {
                "speaker": seg.speaker_display,
                "start": seg.start,
                "end": seg.end,
                "quote": seg.text,
                "segment_refs": {
                    "segment_db_ids": [seg.segment_db_id] if seg.segment_db_id else [],
                    "segment_uuids": [seg.segment_uuid] if seg.segment_uuid else [],
                    "segment_indexes": [seg.segment_index],
                },
            }
        )
    return unique


def _dedupe_phrases(phrases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    for phrase in phrases:
        tokens = set(phrase["tokens"])
        should_add = True
        for existing in deduped:
            existing_tokens = set(existing["tokens"])
            if not tokens or not existing_tokens:
                continue
            overlap = len(tokens & existing_tokens) / len(tokens | existing_tokens)
            contains = phrase["phrase"] in existing["phrase"] or existing["phrase"] in phrase["phrase"]
            if overlap >= 0.85 or contains:
                score_diff = abs(phrase["score"]["total"] - existing["score"]["total"])
                if score_diff <= 0.05:
                    should_add = False
                break
        if should_add:
            deduped.append(phrase)
    return deduped
