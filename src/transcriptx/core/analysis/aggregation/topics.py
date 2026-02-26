"""
Group aggregation for topic modeling.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from transcriptx.core.analysis.aggregation.rows import (
    _fallback_canonical_id,
    session_row_from_result,
)
from transcriptx.core.analysis.aggregation.speaker_utils import (  # type: ignore[import]
    resolve_canonical_speaker,
)
from transcriptx.core.analysis.topic_modeling.lda import (  # type: ignore[import]
    perform_enhanced_lda_analysis,
)
from transcriptx.core.domain.transcript_set import TranscriptSet  # type: ignore[import]
from transcriptx.core.pipeline.result_envelope import (  # type: ignore[import]
    PerTranscriptResult,
)
from transcriptx.core.pipeline.speaker_normalizer import (  # type: ignore[import]
    CanonicalSpeakerMap,
)
from transcriptx.core.utils.nlp_utils import (  # type: ignore[import]
    has_meaningful_content,
    preprocess_for_topic_modeling,
)
from transcriptx.core.utils.path_utils import (  # type: ignore[import]
    get_canonical_base_name,
)
from transcriptx.io.transcript_service import TranscriptService  # type: ignore[import]
from transcriptx.io.transcript_loader import extract_ignored_speakers_from_transcript


def _extract_transcript_file_id(segments: List[Dict[str, Any]]) -> str | None:
    for segment in segments:
        value = segment.get("transcript_file_id")
        if value is not None:
            return str(value)
    return None


def aggregate_topics_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
    aggregations: Dict[str, Any] | None = None,
) -> Dict[str, Any] | None:
    """
    Fit a group-level topic model and aggregate by session and speaker.
    """
    transcript_service = TranscriptService(enable_cache=True)

    texts: List[str] = []
    session_ids: List[str] = []
    session_paths: List[str] = []
    session_path_map: Dict[str, str] = {}
    speakers: List[str | None] = []
    time_labels: List[float] = []

    session_meta: Dict[str, Dict[str, Any]] = {}
    path_meta: Dict[str, Dict[str, Any]] = {}
    display_to_canonical_global = {
        display: canonical_id
        for canonical_id, display in canonical_speaker_map.canonical_to_display.items()
    }

    for result in per_transcript_results:
        transcript_path = result.transcript_path
        segments = transcript_service.load_segments(transcript_path, use_cache=True)
        if not segments:
            continue
        ignored_ids = set(extract_ignored_speakers_from_transcript(transcript_path))

        transcript_file_id = _extract_transcript_file_id(segments)
        session_id = transcript_file_id or get_canonical_base_name(transcript_path)
        session_meta.setdefault(
            session_id,
            session_row_from_result(
                result, transcript_set, session_path=transcript_path
            ),
        )
        path_meta.setdefault(
            transcript_path,
            session_row_from_result(
                result, transcript_set, session_path=transcript_path
            ),
        )

        for idx, segment in enumerate(segments):
            text = segment.get("text", "")
            if not has_meaningful_content(
                text, preprocessing_func=preprocess_for_topic_modeling
            ):
                continue

            processed = preprocess_for_topic_modeling(text)
            if not processed:
                continue

            speaker_info = resolve_canonical_speaker(
                segment, transcript_path, canonical_speaker_map, ignored_ids
            )
            speaker_display = speaker_info[1] if speaker_info else None

            texts.append(processed)
            session_ids.append(session_id)
            session_paths.append(transcript_path)
            session_path_map.setdefault(session_id, transcript_path)
            speakers.append(speaker_display)
            time_labels.append(float(segment.get("start", idx)))

    if len(texts) < 3:
        return None

    lda_results = perform_enhanced_lda_analysis(texts, speakers, time_labels)
    topics = lda_results.get("topics", [])
    doc_topics = lda_results.get("doc_topics")
    if doc_topics is None:
        return None

    topic_terms = {
        topic["topic_id"]: ", ".join(topic.get("words", [])) for topic in topics
    }

    session_sums: Dict[str, List[float]] = defaultdict(list)
    speaker_sums: Dict[str, List[float]] = defaultdict(list)
    session_counts: Dict[str, int] = defaultdict(int)
    speaker_counts: Dict[str, int] = defaultdict(int)

    for idx, topic_dist in enumerate(doc_topics):
        session_id = session_ids[idx]
        speaker = speakers[idx]
        topic_vector = list(map(float, topic_dist))

        if session_id not in session_sums:
            session_sums[session_id] = [0.0] * len(topic_vector)
        session_counts[session_id] += 1
        session_sums[session_id] = [
            acc + value for acc, value in zip(session_sums[session_id], topic_vector)
        ]

        if speaker:
            if speaker not in speaker_sums:
                speaker_sums[speaker] = [0.0] * len(topic_vector)
            speaker_counts[speaker] += 1
            speaker_sums[speaker] = [
                acc + value for acc, value in zip(speaker_sums[speaker], topic_vector)
            ]

    session_rows: List[Dict[str, Any]] = []
    for session_id, sums in session_sums.items():
        count = session_counts[session_id] or 1
        for topic_id, total in enumerate(sums):
            session_rows.append(
                {
                    "session_id": session_id,
                    "session_path": session_path_map.get(session_id, ""),
                    "topic_id": topic_id,
                    "topic_share": total / count,
                    "top_terms": topic_terms.get(topic_id, ""),
                }
            )

    speaker_rows: List[Dict[str, Any]] = []
    for speaker, sums in speaker_sums.items():
        count = speaker_counts[speaker] or 1
        for topic_id, total in enumerate(sums):
            speaker_rows.append(
                {
                    "speaker": speaker,
                    "topic_id": topic_id,
                    "topic_share": total / count,
                    "top_terms": topic_terms.get(topic_id, ""),
                }
            )

    session_rows.sort(
        key=lambda row: (row["session_id"], -row["topic_share"], row["topic_id"])
    )
    speaker_rows.sort(
        key=lambda row: (row["speaker"], -row["topic_share"], row["topic_id"])
    )

    overall_topics = []
    total_docs = len(doc_topics)
    if total_docs:
        overall_sums = [0.0] * len(doc_topics[0])
        for topic_dist in doc_topics:
            overall_sums = [
                acc + float(value) for acc, value in zip(overall_sums, topic_dist)
            ]
        overall_topics = [
            {"topic_id": idx, "topic_share": total / total_docs}
            for idx, total in enumerate(overall_sums)
        ]

    top_sessions_per_topic: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for row in session_rows:
        top_sessions_per_topic[row["topic_id"]].append(row)
    top_sessions_per_topic = {
        topic_id: sorted(rows, key=lambda r: r["topic_share"], reverse=True)[:3]
        for topic_id, rows in top_sessions_per_topic.items()
    }

    top_speakers_per_topic: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for row in speaker_rows:
        top_speakers_per_topic[row["topic_id"]].append(row)
    top_speakers_per_topic = {
        topic_id: sorted(rows, key=lambda r: r["topic_share"], reverse=True)[:3]
        for topic_id, rows in top_speakers_per_topic.items()
    }

    summary = {
        "topics": topics,
        "overall_topic_prevalence": overall_topics,
        "top_sessions_per_topic": top_sessions_per_topic,
        "top_speakers_per_topic": top_speakers_per_topic,
        "group_uuid": transcript_set.metadata.get("group_uuid"),
        "transcript_set_key": transcript_set.key,
        "transcript_set_name": transcript_set.name,
    }

    tables: Dict[str, List[Dict[str, Any]]] = {
        "by_session": session_rows,
        "by_speaker": speaker_rows,
    }

    canonical_session_rows: List[Dict[str, Any]] = []
    for entry in session_rows:
        row = dict(entry)
        meta = session_meta.get(entry["session_id"]) or path_meta.get(
            entry.get("session_path", "")
        )
        if meta:
            row.setdefault("transcript_id", meta.get("transcript_id"))
            row.setdefault("order_index", meta.get("order_index"))
            row.setdefault("run_relpath", meta.get("run_relpath"))
        canonical_session_rows.append(row)

    canonical_speaker_rows: List[Dict[str, Any]] = []
    for entry in speaker_rows:
        row = dict(entry)
        speaker = row.pop("speaker", None)
        canonical_id = display_to_canonical_global.get(
            speaker, _fallback_canonical_id(str(speaker))
        )
        row["canonical_speaker_id"] = canonical_id
        row["display_name"] = canonical_speaker_map.canonical_to_display.get(
            canonical_id, speaker
        )
        canonical_speaker_rows.append(row)

    canonical_session_rows.sort(
        key=lambda row: (row.get("order_index", 0), -row.get("topic_share", 0.0))
    )
    canonical_speaker_rows.sort(
        key=lambda row: (row.get("display_name", ""), -row.get("topic_share", 0.0))
    )

    return {
        "session_rows": canonical_session_rows,
        "speaker_rows": canonical_speaker_rows,
    }
