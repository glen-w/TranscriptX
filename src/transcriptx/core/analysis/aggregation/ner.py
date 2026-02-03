"""
Group aggregation for NER (entity registry).
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from transcriptx.core.analysis.aggregation.speaker_utils import (  # type: ignore[import]
    resolve_canonical_speaker,
)
from transcriptx.core.analysis.ner import extract_named_entities  # type: ignore[import]
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


def _canonicalize_entity(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    return " ".join(cleaned.split())


def _extract_transcript_file_id(segments: List[Dict[str, Any]]) -> str | None:
    for segment in segments:
        value = segment.get("transcript_file_id")
        if value is not None:
            return str(value)
    return None


def _segment_id(session_id: str, segment: Dict[str, Any], index: int) -> str:
    if segment.get("id") is not None:
        return str(segment.get("id"))
    if segment.get("start_ms") is not None:
        return str(segment.get("start_ms"))
    return f"{session_id}:{index}"


def aggregate_ner_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any], Dict[Tuple[str, str], Dict[str, Any]]] | None:
    """
    Aggregate NER across transcripts into overall/session/speaker tables.

    Returns:
        (tables, summary, mentions_index) or None when no entities are found.
    """
    transcript_service = TranscriptService(enable_cache=True)

    overall: Dict[Tuple[str, str], Dict[str, Any]] = {}
    by_session: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
    by_speaker: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    mentions_index: Dict[Tuple[str, str], Dict[str, Any]] = {}

    excluded_unidentified_mentions = 0
    entity_type_counts: Dict[str, int] = defaultdict(int)

    for result in per_transcript_results:
        transcript_path = result.transcript_path
        segments = transcript_service.load_segments(transcript_path, use_cache=True)
        if not segments:
            continue

        transcript_file_id = _extract_transcript_file_id(segments)
        session_id = transcript_file_id or get_canonical_base_name(transcript_path)
        session_path = transcript_path

        for idx, segment in enumerate(segments):
            text = segment.get("text", "")
            if not text or not text.strip():
                continue

            seg_id = _segment_id(session_id, segment, idx)
            speaker_info = resolve_canonical_speaker(
                segment, transcript_path, canonical_speaker_map
            )
            speaker_display = speaker_info[1] if speaker_info else None

            entities = extract_named_entities(text)
            if not entities:
                continue

            normalized_entities: List[Tuple[str, str]] = []
            for entity_text, entity_type in entities:
                normalized = _canonicalize_entity(entity_text)
                if not normalized:
                    continue
                normalized_entities.append((normalized, entity_type))

            if not normalized_entities:
                continue

            mentions_index[(session_id, seg_id)] = {
                "speaker": speaker_display,
                "entities": list(normalized_entities),
            }

            for entity, entity_type in normalized_entities:
                overall_key = (entity, entity_type)
                overall_entry = overall.setdefault(
                    overall_key,
                    {
                        "entity": entity,
                        "entity_type": entity_type,
                        "mentions": 0,
                        "sessions": set(),
                        "speakers": set(),
                    },
                )
                overall_entry["mentions"] += 1
                overall_entry["sessions"].add(session_id)
                if speaker_display is not None:
                    overall_entry["speakers"].add(speaker_display)
                else:
                    excluded_unidentified_mentions += 1

                entity_type_counts[entity_type] += 1

                session_key = (session_id, session_path, entity, entity_type)
                session_entry = by_session.setdefault(
                    session_key,
                    {
                        "session_id": session_id,
                        "session_path": session_path,
                        "entity": entity,
                        "entity_type": entity_type,
                        "mentions": 0,
                        "segments": set(),
                    },
                )
                session_entry["mentions"] += 1
                session_entry["segments"].add(seg_id)

                if speaker_display is None:
                    continue

                speaker_key = (speaker_display, entity, entity_type)
                speaker_entry = by_speaker.setdefault(
                    speaker_key,
                    {
                        "speaker": speaker_display,
                        "entity": entity,
                        "entity_type": entity_type,
                        "mentions": 0,
                        "segments": set(),
                    },
                )
                speaker_entry["mentions"] += 1
                speaker_entry["segments"].add(seg_id)

    if not overall:
        return None

    overall_rows: List[Dict[str, Any]] = []
    for entry in overall.values():
        overall_rows.append(
            {
                "entity": entry["entity"],
                "entity_type": entry["entity_type"],
                "mentions": entry["mentions"],
                "sessions_count": len(entry["sessions"]),
                "speakers_count": len(entry["speakers"]),
            }
        )

    session_rows: List[Dict[str, Any]] = []
    for entry in by_session.values():
        session_rows.append(
            {
                "session_id": entry["session_id"],
                "session_path": entry["session_path"],
                "entity": entry["entity"],
                "entity_type": entry["entity_type"],
                "mentions": entry["mentions"],
                "unique_segments": len(entry["segments"]),
            }
        )

    speaker_rows: List[Dict[str, Any]] = []
    for entry in by_speaker.values():
        speaker_rows.append(
            {
                "speaker": entry["speaker"],
                "entity": entry["entity"],
                "entity_type": entry["entity_type"],
                "mentions": entry["mentions"],
                "unique_segments": len(entry["segments"]),
            }
        )

    overall_rows.sort(key=lambda row: (-row["mentions"], row["entity"], row["entity_type"]))
    session_rows.sort(
        key=lambda row: (row["session_id"], -row["mentions"], row["entity"])
    )
    speaker_rows.sort(
        key=lambda row: (row["speaker"], -row["mentions"], row["entity"])
    )

    top_entities = overall_rows[:10]
    total_mentions = sum(row["mentions"] for row in overall_rows)

    summary = {
        "top_entities": top_entities,
        "entity_counts_by_type": dict(sorted(entity_type_counts.items())),
        "total_mentions": total_mentions,
        "excluded_unidentified_mentions": excluded_unidentified_mentions,
        "group_uuid": transcript_set.metadata.get("group_uuid"),
        "transcript_set_key": transcript_set.key,
        "transcript_set_name": transcript_set.name,
    }

    tables: Dict[str, List[Dict[str, Any]]] = {
        "overall": overall_rows,
        "by_session": session_rows,
        "by_speaker": speaker_rows,
    }

    return tables, summary, mentions_index
