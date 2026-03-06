"""
Group aggregation for BERTopic.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from transcriptx.core.analysis.aggregation.rows import (
    _fallback_canonical_id,
    session_row_from_result,
)
from transcriptx.core.analysis.aggregation.schema import get_transcript_id
from transcriptx.core.analysis.aggregation.speaker_utils import (  # type: ignore[import]
    resolve_canonical_speaker,
)
from transcriptx.core.analysis.aggregation.warnings import build_warning
from transcriptx.core.analysis.bertopic.utils import (
    build_doc_topic_data,
    build_topic_objects,
)
from transcriptx.core.domain.transcript_set import TranscriptSet  # type: ignore[import]
from transcriptx.core.pipeline.result_envelope import (  # type: ignore[import]
    PerTranscriptResult,
)
from transcriptx.core.pipeline.speaker_normalizer import (  # type: ignore[import]
    CanonicalSpeakerMap,
)
from transcriptx.core.utils.lazy_imports import optional_import
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.nlp_utils import (  # type: ignore[import]
    has_meaningful_content,
    preprocess_for_topic_modeling,
)
from transcriptx.core.utils.path_utils import (  # type: ignore[import]
    get_canonical_base_name,
)
from transcriptx.io import save_json  # type: ignore[import]
from transcriptx.io.transcript_service import TranscriptService  # type: ignore[import]
from transcriptx.io.transcript_loader import extract_ignored_speakers_from_transcript


def _extract_transcript_file_id(segments: List[Dict[str, Any]]) -> str | None:
    for segment in segments:
        value = segment.get("transcript_file_id")
        if value is not None:
            return str(value)
    return None


def _validate_group_payload(
    topics: list[dict[str, Any]],
    doc_topic_data: list[dict[str, Any]],
) -> list[str]:
    warnings: list[str] = []
    if not isinstance(topics, list):
        warnings.append("Group bertopic topics payload is not a list.")
    else:
        for idx, topic in enumerate(topics):
            if not isinstance(topic, dict):
                warnings.append(f"Group bertopic topic {idx} is not an object.")
                continue
            if "topic_id" not in topic or "words" not in topic:
                warnings.append(f"Group bertopic topic {idx} missing topic_id/words.")
                continue
            words = topic.get("words")
            weights = topic.get("weights")
            if not isinstance(words, list):
                warnings.append(f"Group bertopic topic {idx} words is not a list.")
            if weights is not None and isinstance(weights, list):
                if len(weights) != len(words):
                    warnings.append(
                        f"Group bertopic topic {idx} weights length mismatch."
                    )

    if not isinstance(doc_topic_data, list):
        warnings.append("Group bertopic doc_topic_data payload is not a list.")
    else:
        for idx, row in enumerate(doc_topic_data):
            if not isinstance(row, dict):
                warnings.append(
                    f"Group bertopic doc_topic_data {idx} is not an object."
                )
                continue
            if "doc_index" not in row or "dominant_topic" not in row:
                warnings.append(
                    f"Group bertopic doc_topic_data {idx} missing doc_index/dominant_topic."
                )
            if "segment_index" not in row:
                warnings.append(
                    f"Group bertopic doc_topic_data {idx} missing segment_index."
                )
            if "transcript_id" not in row and "session_name" not in row:
                warnings.append(
                    f"Group bertopic doc_topic_data {idx} missing transcript_id/session_name."
                )
    return warnings


def aggregate_bertopic_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
    aggregations: Dict[str, Any] | None = None,
) -> Dict[str, Any] | None:
    """
    Fit a group-level BERTopic model and aggregate by session and speaker.
    """
    transcript_service = TranscriptService(enable_cache=True)

    texts: List[str] = []
    session_ids: List[str] = []
    speakers: List[str | None] = []
    time_labels: List[float] = []
    doc_extra_fields: List[Dict[str, Any]] = []

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
        transcript_id = get_transcript_id(result, transcript_set)
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
            speakers.append(speaker_display)
            time_labels.append(float(segment.get("start", idx)))
            doc_extra_fields.append(
                {
                    "segment_index": idx,
                    "transcript_id": transcript_id,
                    "session_name": session_id,
                }
            )

    if len(texts) < 3:
        return {
            "warning": build_warning(
                code="INSUFFICIENT_DATA",
                message="Not enough segments for group BERTopic aggregation.",
                aggregation_key="bertopic",
                details={"texts_count": len(texts)},
            )
        }

    try:
        bertopic_module = optional_import(
            "bertopic", "BERTopic topic modeling", "bertopic", auto_install=True
        )
    except ImportError as exc:
        return {
            "warning": build_warning(
                code="MISSING_DEP",
                message=(
                    f"{exc} If install fails on your platform, try upgrading pip and "
                    "installing build tools."
                ),
                aggregation_key="bertopic",
                missing_deps=["bertopic"],
            )
        }

    config = get_config()
    bertopic_cfg = getattr(config.analysis, "bertopic", None)
    model_kwargs: Dict[str, Any] = {}
    if bertopic_cfg:
        if getattr(bertopic_cfg, "embedding_model", None):
            model_kwargs["embedding_model"] = bertopic_cfg.embedding_model
        if getattr(bertopic_cfg, "min_topic_size", None):
            model_kwargs["min_topic_size"] = bertopic_cfg.min_topic_size
        nr_topics = getattr(bertopic_cfg, "nr_topics", None)
        if isinstance(nr_topics, str):
            if nr_topics.isdigit():
                model_kwargs["nr_topics"] = int(nr_topics)
            elif nr_topics:
                model_kwargs["nr_topics"] = nr_topics
        elif isinstance(nr_topics, int):
            model_kwargs["nr_topics"] = nr_topics
        if getattr(bertopic_cfg, "top_n_words", None):
            model_kwargs["top_n_words"] = bertopic_cfg.top_n_words
        if getattr(bertopic_cfg, "calculate_probabilities", None):
            model_kwargs["calculate_probabilities"] = True

    BERTopic = bertopic_module.BERTopic
    model = BERTopic(**model_kwargs)
    topic_assignments, topic_probs = model.fit_transform(texts)

    topics = build_topic_objects(
        model,
        top_n_words=getattr(bertopic_cfg, "top_n_words", 10) if bertopic_cfg else 10,
        label_words=getattr(bertopic_cfg, "label_words", 3) if bertopic_cfg else 3,
        include_outlier=any(int(t) == -1 for t in topic_assignments),
    )
    doc_topic_data, meta = build_doc_topic_data(
        topic_assignments=topic_assignments,
        topic_probs=topic_probs,
        texts=texts,
        speaker_labels=[str(s) if s is not None else "" for s in speakers],
        time_labels=time_labels,
        doc_extra_fields=doc_extra_fields,
    )
    meta.setdefault("texts_count", len(texts))
    meta["group_uuid"] = transcript_set.metadata.get("group_uuid")
    meta["transcript_set_key"] = transcript_set.key
    meta["transcript_set_name"] = transcript_set.name

    payload_warnings = _validate_group_payload(topics, doc_topic_data)
    if payload_warnings:
        return {
            "warning": build_warning(
                code="PAYLOAD_SHAPE_UNSUPPORTED",
                message="Group BERTopic payload validation failed.",
                aggregation_key="bertopic",
                details={"warnings": payload_warnings},
            )
        }

    group_output_dir = transcript_set.metadata.get("group_output_dir")
    if not group_output_dir:
        return {
            "warning": build_warning(
                code="MISSING_ARTIFACT",
                message="Group output directory missing for BERTopic aggregation.",
                aggregation_key="bertopic",
                details={"missing_keys": ["group_output_dir"]},
            )
        }
    agg_dir = Path(str(group_output_dir)) / "bertopic"
    agg_dir.mkdir(parents=True, exist_ok=True)
    save_json(topics, str(agg_dir / "group_bertopic_topics.json"))
    save_json(doc_topic_data, str(agg_dir / "group_bertopic_doc_topics.json"))
    save_json(meta, str(agg_dir / "group_bertopic_meta.json"))

    topic_terms = {
        topic.get("topic_id"): ", ".join(topic.get("words", [])) for topic in topics
    }
    session_counts: dict[str, int] = defaultdict(int)
    speaker_counts: dict[str, int] = defaultdict(int)
    session_topic_counts: dict[str, dict[int, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    speaker_topic_counts: dict[str, dict[int, int]] = defaultdict(
        lambda: defaultdict(int)
    )

    for row in doc_topic_data:
        session_id = str(row.get("session_name", ""))
        speaker = str(row.get("speaker", ""))
        topic_id = int(row.get("dominant_topic", -1))
        session_counts[session_id] += 1
        speaker_counts[speaker] += 1
        session_topic_counts[session_id][topic_id] += 1
        speaker_topic_counts[speaker][topic_id] += 1

    session_rows: List[Dict[str, Any]] = []
    for session_id, topic_counts in session_topic_counts.items():
        total = session_counts.get(session_id, 0)
        for topic_id, count in topic_counts.items():
            session_rows.append(
                {
                    "session_id": session_id,
                    "topic_id": int(topic_id),
                    "topic_share": (count / total) if total else 0.0,
                    "top_terms": topic_terms.get(topic_id, ""),
                }
            )

    speaker_rows: List[Dict[str, Any]] = []
    for speaker, topic_counts in speaker_topic_counts.items():
        total = speaker_counts.get(speaker, 0)
        for topic_id, count in topic_counts.items():
            speaker_rows.append(
                {
                    "speaker": speaker,
                    "topic_id": int(topic_id),
                    "topic_share": (count / total) if total else 0.0,
                    "top_terms": topic_terms.get(topic_id, ""),
                }
            )

    canonical_session_rows: List[Dict[str, Any]] = []
    for entry in session_rows:
        row = dict(entry)
        meta_row = session_meta.get(entry["session_id"]) or path_meta.get(
            entry.get("session_path", "")
        )
        if meta_row:
            row.setdefault("transcript_id", meta_row.get("transcript_id"))
            row.setdefault("order_index", meta_row.get("order_index"))
            row.setdefault("run_relpath", meta_row.get("run_relpath"))
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
