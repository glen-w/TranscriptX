"""
Helpers for BERTopic output shaping.
"""

from __future__ import annotations

from typing import Any, Iterable


DEFAULT_TOP_N_WORDS = 10
DEFAULT_LABEL_WORDS = 3


def _coerce_float_list(values: Any) -> list[float] | None:
    if values is None:
        return None
    try:
        return [float(v) for v in values]
    except Exception:
        return None


def _get_topic_sizes(model: Any) -> dict[int, int]:
    try:
        info = model.get_topic_info()
    except Exception:
        return {}
    sizes: dict[int, int] = {}
    try:
        for _, row in info.iterrows():
            topic_id = row.get("Topic") if hasattr(row, "get") else row["Topic"]
            count = row.get("Count") if hasattr(row, "get") else row["Count"]
            if topic_id is None or count is None:
                continue
            sizes[int(topic_id)] = int(count)
    except Exception:
        return {}
    return sizes


def build_topic_objects(
    model: Any,
    *,
    top_n_words: int = DEFAULT_TOP_N_WORDS,
    label_words: int = DEFAULT_LABEL_WORDS,
    include_outlier: bool = True,
) -> list[dict[str, Any]]:
    topics: list[dict[str, Any]] = []
    topic_sizes = _get_topic_sizes(model)
    topic_map = model.get_topics() if model is not None else {}

    for topic_id, word_weights in (topic_map or {}).items():
        if int(topic_id) == -1:
            continue
        words: list[str] = []
        weights: list[float] | None = []
        if word_weights:
            for word, weight in word_weights[:top_n_words]:
                words.append(str(word))
                weights.append(float(weight))
        if not words:
            weights = None
        label_candidates = words[:label_words]
        label = ", ".join(label_candidates) if label_candidates else f"Topic {topic_id}"
        topics.append(
            {
                "topic_id": int(topic_id),
                "words": words,
                "weights": weights,
                "label": label,
                "label_source": "ctfidf_top_words",
                "size": topic_sizes.get(int(topic_id)),
            }
        )

    if include_outlier:
        topics.append(
            {
                "topic_id": -1,
                "words": [],
                "weights": None,
                "label": "Outlier",
                "label_source": "synthetic_outlier",
                "size": topic_sizes.get(-1),
            }
        )

    return topics


def build_doc_topic_data(
    *,
    topic_assignments: Iterable[int],
    topic_probs: Any,
    texts: list[str],
    speaker_labels: list[str],
    time_labels: list[float],
    doc_extra_fields: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    doc_topic_data: list[dict[str, Any]] = []
    meta: dict[str, Any] = {}
    doc_index_to_segment_index: dict[str, int] = {}
    include_segment_map = True
    if doc_extra_fields:
        for fields in doc_extra_fields:
            if "transcript_id" in fields or "session_name" in fields:
                include_segment_map = False
                break
    all_outliers = True

    for idx, (text, speaker, time, topic_id) in enumerate(
        zip(texts, speaker_labels, time_labels, topic_assignments, strict=False)
    ):
        extra_fields = doc_extra_fields[idx] if doc_extra_fields else {}
        row_probs = None
        if topic_probs is not None:
            try:
                row_probs = _coerce_float_list(topic_probs[idx])
            except Exception:
                row_probs = None

        if row_probs is not None and len(row_probs) > 0:
            confidence = float(max(row_probs))
        else:
            confidence = 0.0 if int(topic_id) == -1 else 1.0

        if int(topic_id) != -1:
            all_outliers = False

        row = {
            "doc_index": idx,
            "text": text,
            "speaker": speaker,
            "time": time,
            "dominant_topic": int(topic_id),
            "topic_distribution": row_probs if row_probs is not None else None,
            "confidence": confidence,
        }
        if extra_fields:
            row.update(extra_fields)
        doc_topic_data.append(row)

        if include_segment_map:
            segment_index = extra_fields.get("segment_index")
            if segment_index is not None:
                doc_index_to_segment_index[str(idx)] = int(segment_index)

    if include_segment_map and doc_index_to_segment_index:
        meta["doc_index_to_segment_index"] = doc_index_to_segment_index
    if doc_topic_data and all_outliers:
        meta["warning"] = "All documents classified as outliers"

    return doc_topic_data, meta
