"""
Group aggregation for entity-based sentiment.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from transcriptx.core.analysis.aggregation.rows import (
    _fallback_canonical_id,
    session_row_from_result,
)
from transcriptx.core.analysis.sentiment import score_sentiment  # type: ignore[import]
from transcriptx.core.domain.transcript_set import TranscriptSet  # type: ignore[import]
from transcriptx.core.pipeline.result_envelope import (  # type: ignore[import]
    PerTranscriptResult,
)
from transcriptx.core.pipeline.speaker_normalizer import (  # type: ignore[import]
    CanonicalSpeakerMap,
)
from transcriptx.core.utils.path_utils import (  # type: ignore[import]
    get_canonical_base_name,
)
from transcriptx.io.transcript_service import TranscriptService  # type: ignore[import]


def _extract_sentiment_payload(module_results: Dict[str, Any]) -> Dict[str, Any]:
    sentiment_result = module_results.get("sentiment", {})
    if not isinstance(sentiment_result, dict):
        return {}
    payload = sentiment_result.get("payload") or sentiment_result.get("results") or {}
    if isinstance(payload, dict) and payload:
        return payload
    return sentiment_result if isinstance(sentiment_result, dict) else {}


def _segment_id(session_id: str, segment: Dict[str, Any], index: int) -> str:
    if segment.get("id") is not None:
        return str(segment.get("id"))
    if segment.get("start_ms") is not None:
        return str(segment.get("start_ms"))
    return f"{session_id}:{index}"


def _extract_transcript_file_id(segments: List[Dict[str, Any]]) -> str | None:
    for segment in segments:
        value = segment.get("transcript_file_id")
        if value is not None:
            return str(value)
    return None


def _build_sentiment_map(
    result: PerTranscriptResult, transcript_service: TranscriptService
) -> Tuple[str, str, Dict[Tuple[str, str], Dict[str, float]]]:
    segments = []
    payload = _extract_sentiment_payload(result.module_results)
    segments_with_sentiment = payload.get("segments_with_sentiment")
    if isinstance(segments_with_sentiment, list):
        segments = segments_with_sentiment
    else:
        segments = transcript_service.load_segments(
            result.transcript_path, use_cache=True
        )
        for seg in segments:
            text = seg.get("text", "")
            seg["sentiment"] = score_sentiment(text, preprocess=True)

    transcript_file_id = _extract_transcript_file_id(segments)
    session_id = transcript_file_id or get_canonical_base_name(result.transcript_path)
    session_path = result.transcript_path

    sentiment_map: Dict[Tuple[str, str], Dict[str, float]] = {}
    for idx, segment in enumerate(segments):
        sentiment = segment.get("sentiment") or {}
        seg_id = _segment_id(session_id, segment, idx)
        sentiment_map[(session_id, seg_id)] = {
            "compound": float(sentiment.get("compound", 0.0) or 0.0),
            "pos": float(sentiment.get("pos", 0.0) or 0.0),
            "neu": float(sentiment.get("neu", 0.0) or 0.0),
            "neg": float(sentiment.get("neg", 0.0) or 0.0),
            "session_path": session_path,
        }

    return session_id, session_path, sentiment_map


def aggregate_entity_sentiment_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
    aggregations: Dict[str, Any] | None = None,
) -> Dict[str, Any] | None:
    """
    Aggregate sentiment for entities across transcripts.
    """
    mentions_index = ((aggregations or {}).get("ner") or {}).get("mentions_index")
    if not mentions_index:
        return None

    transcript_service = TranscriptService(enable_cache=True)

    sentiment_by_segment: Dict[Tuple[str, str], Dict[str, Any]] = {}
    session_paths: Dict[str, str] = {}
    session_meta: Dict[str, Dict[str, Any]] = {}
    path_meta: Dict[str, Dict[str, Any]] = {}
    display_to_canonical_global = {
        display: canonical_id
        for canonical_id, display in canonical_speaker_map.canonical_to_display.items()
    }

    for result in per_transcript_results:
        session_id, session_path, sentiment_map = _build_sentiment_map(
            result, transcript_service
        )
        session_paths[session_id] = session_path
        session_meta.setdefault(
            session_id,
            session_row_from_result(result, transcript_set, session_path=session_path),
        )
        path_meta.setdefault(
            session_path,
            session_row_from_result(result, transcript_set, session_path=session_path),
        )
        sentiment_by_segment.update(sentiment_map)

    if not sentiment_by_segment:
        return None

    by_session: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    by_speaker: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    global_agg: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for (session_id, segment_id), payload in mentions_index.items():
        sentiment = sentiment_by_segment.get((session_id, segment_id))
        if not sentiment:
            continue

        speaker = payload.get("speaker")
        entities = payload.get("entities") or []
        session_path = sentiment.get("session_path") or session_paths.get(
            session_id, ""
        )

        for entity, entity_type in entities:
            session_key = (session_id, entity, entity_type)
            session_entry = by_session.setdefault(
                session_key,
                {
                    "session_id": session_id,
                    "session_path": session_path,
                    "entity": entity,
                    "entity_type": entity_type,
                    "mentions": 0,
                    "sum_compound": 0.0,
                    "sum_pos": 0.0,
                    "sum_neu": 0.0,
                    "sum_neg": 0.0,
                },
            )
            session_entry["mentions"] += 1
            session_entry["sum_compound"] += sentiment["compound"]
            session_entry["sum_pos"] += sentiment["pos"]
            session_entry["sum_neu"] += sentiment["neu"]
            session_entry["sum_neg"] += sentiment["neg"]

            global_key = (entity, entity_type)
            global_entry = global_agg.setdefault(
                global_key,
                {
                    "entity": entity,
                    "entity_type": entity_type,
                    "mentions": 0,
                    "sum_compound": 0.0,
                    "sum_pos": 0.0,
                    "sum_neu": 0.0,
                    "sum_neg": 0.0,
                },
            )
            global_entry["mentions"] += 1
            global_entry["sum_compound"] += sentiment["compound"]
            global_entry["sum_pos"] += sentiment["pos"]
            global_entry["sum_neu"] += sentiment["neu"]
            global_entry["sum_neg"] += sentiment["neg"]

            if speaker:
                speaker_key = (speaker, entity, entity_type)
                speaker_entry = by_speaker.setdefault(
                    speaker_key,
                    {
                        "speaker": speaker,
                        "entity": entity,
                        "entity_type": entity_type,
                        "mentions": 0,
                        "sum_compound": 0.0,
                        "sum_pos": 0.0,
                        "sum_neu": 0.0,
                        "sum_neg": 0.0,
                    },
                )
                speaker_entry["mentions"] += 1
                speaker_entry["sum_compound"] += sentiment["compound"]
                speaker_entry["sum_pos"] += sentiment["pos"]
                speaker_entry["sum_neu"] += sentiment["neu"]
                speaker_entry["sum_neg"] += sentiment["neg"]

    if not global_agg:
        return None

    def _row_from_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        mentions = entry["mentions"] or 1
        return {
            "mentions": entry["mentions"],
            "mean_sentiment": entry["sum_compound"] / mentions,
            "pos": entry["sum_pos"] / mentions,
            "neu": entry["sum_neu"] / mentions,
            "neg": entry["sum_neg"] / mentions,
        }

    session_rows: List[Dict[str, Any]] = []
    for entry in by_session.values():
        base = {
            "session_id": entry["session_id"],
            "session_path": entry["session_path"],
            "entity": entry["entity"],
            "entity_type": entry["entity_type"],
        }
        base.update(_row_from_entry(entry))
        meta = session_meta.get(entry["session_id"]) or path_meta.get(
            entry["session_path"]
        )
        if meta:
            base.setdefault("transcript_id", meta.get("transcript_id"))
            base.setdefault("order_index", meta.get("order_index"))
            base.setdefault("run_relpath", meta.get("run_relpath"))
        session_rows.append(base)

    speaker_rows: List[Dict[str, Any]] = []
    for entry in by_speaker.values():
        speaker = entry["speaker"]
        canonical_id = display_to_canonical_global.get(
            speaker, _fallback_canonical_id(str(speaker))
        )
        base = {
            "canonical_speaker_id": canonical_id,
            "display_name": canonical_speaker_map.canonical_to_display.get(
                canonical_id, speaker
            ),
            "entity": entry["entity"],
            "entity_type": entry["entity_type"],
        }
        base.update(_row_from_entry(entry))
        speaker_rows.append(base)
    session_rows.sort(
        key=lambda row: (row.get("order_index", 0), -row["mentions"], row["entity"])
    )
    speaker_rows.sort(
        key=lambda row: (row.get("display_name", ""), -row["mentions"], row["entity"])
    )

    return {
        "session_rows": session_rows,
        "speaker_rows": speaker_rows,
    }
