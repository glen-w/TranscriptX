"""Shared normalization for highlights/summary (SegmentLite contract)."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from transcriptx.core.analysis.highlights.core import (  # type: ignore[import-untyped]
    SegmentLite,
)


def _segment_lookup_key(segment: Dict[str, Any]) -> str:
    if segment.get("segment_db_id") is not None:
        return f"db:{segment.get('segment_db_id')}"
    if segment.get("segment_uuid"):
        return f"uuid:{segment.get('segment_uuid')}"
    return f"idx:{segment.get('segment_index')}"


def _segment_key_from_parts(
    transcript_key: str, segment_db_id: Optional[int], segment_uuid: Optional[str], segment_index: int
) -> str:
    if segment_db_id is not None:
        return f"db:{segment_db_id}"
    if segment_uuid:
        return f"uuid:{segment_uuid}"
    return f"idx:{transcript_key}:{segment_index}"


def _build_sentiment_map(context: Any) -> Dict[str, float]:
    sentiment_map: Dict[str, float] = {}
    if not context:
        return sentiment_map
    sentiment_result = context.get_analysis_result("sentiment")
    if not isinstance(sentiment_result, dict):
        return sentiment_map
    segments_with_sentiment = sentiment_result.get("segments_with_sentiment") or []
    for seg in segments_with_sentiment:
        if not isinstance(seg, dict):
            continue
        key = _segment_lookup_key(seg)
        sentiment = seg.get("sentiment") or {}
        compound = sentiment.get("compound")
        if compound is not None:
            sentiment_map[key] = float(compound)
    return sentiment_map


def _build_emotion_map(context: Any) -> Dict[str, Dict[str, Any]]:
    emotion_map: Dict[str, Dict[str, Any]] = {}
    if not context:
        return emotion_map
    emotion_result = context.get_analysis_result("emotion")
    if not isinstance(emotion_result, dict):
        return emotion_map
    segments_with_emotion = emotion_result.get("segments_with_emotion") or []
    for seg in segments_with_emotion:
        if not isinstance(seg, dict):
            continue
        key = _segment_lookup_key(seg)
        emotion_map[key] = {
            "nrc_emotion": seg.get("nrc_emotion") or {},
            "context_emotion": seg.get("context_emotion"),
        }
    return emotion_map


def normalize_segments(
    segments: List[Dict[str, Any]],
    *,
    context: Any = None,
    transcript_key: str = "unknown",
) -> List[SegmentLite]:
    sentiment_map = _build_sentiment_map(context)
    emotion_map = _build_emotion_map(context)
    normalized: List[SegmentLite] = []
    for idx, segment in enumerate(segments):
        segment_index = segment.get("segment_index")
        if segment_index is None:
            segment_index = idx
        segment_db_id = segment.get("segment_db_id")
        segment_uuid = segment.get("segment_uuid") or segment.get("uuid")
        segment_key = _segment_key_from_parts(
            transcript_key, segment_db_id, segment_uuid, segment_index
        )
        speaker_display = segment.get("speaker_display") or segment.get("speaker") or ""
        speaker_id = segment.get("speaker_db_id") or segment.get("speaker_id")
        sentiment_compound = None
        emotion_dist = None
        context_emotion = None
        lookup_key = _segment_lookup_key(
            {
                "segment_db_id": segment_db_id,
                "segment_uuid": segment_uuid,
                "segment_index": segment_index,
            }
        )
        if lookup_key in sentiment_map:
            sentiment_compound = sentiment_map[lookup_key]
        else:
            sentiment = segment.get("sentiment") or {}
            compound = sentiment.get("compound")
            if compound is not None:
                sentiment_compound = float(compound)

        if lookup_key in emotion_map:
            emotion_payload = emotion_map[lookup_key]
            emotion_dist = emotion_payload.get("nrc_emotion") or None
            context_emotion = emotion_payload.get("context_emotion")
        else:
            emotion_dist = segment.get("nrc_emotion") or None
            context_emotion = segment.get("context_emotion")

        normalized.append(
            SegmentLite(
                segment_key=segment_key,
                segment_db_id=segment_db_id,
                segment_uuid=segment_uuid,
                segment_index=int(segment_index),
                speaker_display=str(speaker_display),
                speaker_id=speaker_id,
                start=float(segment.get("start", 0.0)),
                end=float(segment.get("end", 0.0)),
                text=str(segment.get("text", "")).strip(),
                sentiment_compound=sentiment_compound,
                emotion_dist=emotion_dist,
                context_emotion=context_emotion,
            )
        )
    return normalized
