"""
Group aggregation for BERTopic.

True data source (locked): refits from pooled **source segments**, not from
transcript-level BERTopic topic artifacts. Per-transcript ``topic_id`` values
are not joined across fits. Member artifacts are used only for activation /
session metadata when needed.

``deps=[]`` is correct: the group model is independently refitted and does not
depend on other aggregation outputs.
"""

from __future__ import annotations

import time
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
from transcriptx.core.analysis.bertopic.deps import (
    EXTRA_NAME,
    embedding_model_policy_check,
    verify_bertopic_import,
)
from transcriptx.core.analysis.bertopic.eligibility import (
    evaluate_bertopic_eligibility,
)
from transcriptx.core.analysis.bertopic.runtime import (
    build_provenance,
)
from transcriptx.core.analysis.bertopic.schema import (
    SCHEMA_VERSION,
    validate_bertopic_artifact_payload,
)
from transcriptx.core.analysis.bertopic.utils import (
    build_doc_topic_data,
)
from transcriptx.core.domain.transcript_set import TranscriptSet  # type: ignore[import]
from transcriptx.core.pipeline.result_envelope import (  # type: ignore[import]
    PerTranscriptResult,
)
from transcriptx.core.pipeline.speaker_normalizer import (  # type: ignore[import]
    CanonicalSpeakerMap,
)
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.nlp_utils import (  # type: ignore[import]
    has_meaningful_content,
    preprocess_for_topic_modeling,
)
from transcriptx.core.utils._path_core import (  # type: ignore[import]
    get_canonical_base_name,
)
from transcriptx.io.speaker_map_resolver import SpeakerMapResolver
from transcriptx.io import save_json  # type: ignore[import]
from transcriptx.io.transcript_service import TranscriptService  # type: ignore[import]


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


def inspect_member_bertopic_activation(
    member_payload: Any,
) -> tuple[bool, list[str]]:
    """
    Inspect a member transcript BERTopic artifact for activation/status only.

    Does not feed topic IDs into the group fit. Unsupported schema versions are
    skipped with a warning; corrupt payloads are rejected with a warning.
    """
    _payload, warnings = validate_bertopic_artifact_payload(
        member_payload, require_topics=False
    )
    if warnings and _payload is None:
        return False, warnings
    return True, warnings


def aggregate_bertopic_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
    aggregations: Dict[str, Any] | None = None,
) -> Dict[str, Any] | None:
    """
    Fit a group-level BERTopic model from pooled source segments and aggregate.

    Ordering: ``(transcript_id ascending, segment_index ascending)``.
    Duplicate texts are retained as separate documents.
    """
    transcript_service = TranscriptService(enable_cache=True)

    texts: List[str] = []
    speakers: List[str | None] = []
    time_labels: List[float] = []
    doc_extra_fields: List[Dict[str, Any]] = []
    pending_docs: List[Dict[str, Any]] = []

    session_meta: Dict[str, Dict[str, Any]] = {}
    path_meta: Dict[str, Dict[str, Any]] = {}
    display_to_canonical_global = {
        display: canonical_id
        for canonical_id, display in canonical_speaker_map.canonical_to_display.items()
    }
    resolver = SpeakerMapResolver()
    member_activation_warnings: List[str] = []

    for result in per_transcript_results:
        # Member bertopic artifacts are activation/status only — not fit inputs.
        member_payload = None
        if isinstance(result.module_results, dict):
            member_payload = result.module_results.get("bertopic")
        if member_payload is not None:
            _ok, warns = inspect_member_bertopic_activation(member_payload)
            for w in warns:
                member_activation_warnings.append(
                    f"{result.transcript_key or result.transcript_path}: {w}"
                )

        transcript_path = result.transcript_path
        segments = transcript_service.load_segments(transcript_path, use_cache=True)
        if not segments:
            continue
        ignored_ids = set(resolver.load_mapping(transcript_path).ignored_speakers)

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

            pending_docs.append(
                {
                    "text": processed,
                    "speaker": speaker_display,
                    "time": float(segment.get("start", idx)),
                    "segment_index": idx,
                    "transcript_id": str(transcript_id),
                    "session_name": session_id,
                }
            )

    # Group ordering: (transcript_id ascending, segment_index ascending).
    pending_docs.sort(key=lambda d: (str(d["transcript_id"]), int(d["segment_index"])))
    for doc in pending_docs:
        texts.append(doc["text"])
        speakers.append(doc["speaker"])
        time_labels.append(doc["time"])
        doc_extra_fields.append(
            {
                "segment_index": doc["segment_index"],
                "transcript_id": doc["transcript_id"],
                "session_name": doc["session_name"],
            }
        )

    eligibility = evaluate_bertopic_eligibility(texts)
    if not eligibility.eligible:
        return {
            "warning": build_warning(
                code="INSUFFICIENT_DATA",
                message="Not enough segments for group BERTopic aggregation.",
                aggregation_key="bertopic",
                details={
                    "texts_count": eligibility.documents_count,
                    "reason": eligibility.reason,
                    "member_activation_warnings": member_activation_warnings,
                },
            )
        }

    bertopic_module, dep_reason = verify_bertopic_import(auto_install=False)
    if bertopic_module is None:
        return {
            "warning": build_warning(
                code="MISSING_DEP",
                message=(
                    f"{dep_reason}. Install with: pip install -e '.[{EXTRA_NAME}]' "
                    "(from a TranscriptX git checkout; not on PyPI)"
                ),
                aggregation_key="bertopic",
                missing_deps=[EXTRA_NAME],
            )
        }

    config = get_config()
    bertopic_cfg = getattr(config.analysis, "bertopic", None)
    embedding_model = (
        getattr(bertopic_cfg, "embedding_model", None) if bertopic_cfg else None
    )
    policy_reason = embedding_model_policy_check(str(embedding_model or ""))
    if policy_reason:
        return {
            "warning": build_warning(
                code="CONFIG",
                message=policy_reason,
                aggregation_key="bertopic",
                details={"reason": policy_reason},
            )
        }

    started = time.perf_counter()
    try:
        from transcriptx.core.utils.bertopic_fit import (
            fit_bertopic_isolated,
        )

        timeout_seconds = None
        if bertopic_cfg is not None:
            raw_timeout = getattr(bertopic_cfg, "timeout_seconds", None)
            if isinstance(raw_timeout, (int, float)):
                timeout_seconds = float(raw_timeout)
        isolated = fit_bertopic_isolated(
            texts, bertopic_cfg, timeout_seconds=timeout_seconds
        )
    except ImportError as exc:
        return {
            "warning": build_warning(
                code="MISSING_DEP",
                message=f"broken_extra:{EXTRA_NAME}: {exc}",
                aggregation_key="bertopic",
                missing_deps=[EXTRA_NAME],
            )
        }
    except Exception as exc:
        msg = str(exc)
        soft = (
            "0 sample" in msg
            or "minimum of 1 is required" in msg
            or "n_samples=0" in msg
        )
        if soft:
            return {
                "warning": build_warning(
                    code="INSUFFICIENT_DATA",
                    message=f"Group BERTopic fit collapsed: {msg}",
                    aggregation_key="bertopic",
                    details={"reason": "insufficient_data_after_fit", "fit_error": msg},
                )
            }
        raise

    if not isolated.ok:
        err = isolated.error or "bertopic_fit_failed"
        soft = (
            "0 sample" in err
            or "minimum of 1 is required" in err
            or "n_samples=0" in err
            or err.startswith("bertopic_native_crash")
            or err.startswith("bertopic_fit_timeout")
        )
        if soft:
            return {
                "warning": build_warning(
                    code="INSUFFICIENT_DATA",
                    message=f"Group BERTopic fit collapsed: {err}",
                    aggregation_key="bertopic",
                    details={
                        "reason": "insufficient_data_after_fit",
                        "fit_error": err,
                        "exit_code": isolated.exit_code,
                    },
                )
            }
        raise RuntimeError(err)

    duration = isolated.duration_seconds or (time.perf_counter() - started)
    topic_assignments = isolated.topic_assignments
    topic_probs = isolated.topic_probs
    topics = isolated.topics
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
    meta["fit_scope"] = "group"
    meta["schema_version"] = SCHEMA_VERSION
    meta["data_source"] = "source_segments_refit"
    if member_activation_warnings:
        meta["member_activation_warnings"] = member_activation_warnings
    package_version = None
    try:
        import importlib.metadata as im

        package_version = im.version("bertopic")
    except Exception:
        package_version = None
    meta["provenance"] = build_provenance(
        embedding_model=embedding_model,
        fit_scope="group",
        duration_seconds=duration,
        package_version=package_version,
    )

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
    overall_topic_counts: dict[int, int] = defaultdict(int)

    for row in doc_topic_data:
        session_id = str(row.get("session_name", ""))
        speaker = str(row.get("speaker", ""))
        topic_id = int(row.get("dominant_topic", -1))
        session_counts[session_id] += 1
        speaker_counts[speaker] += 1
        session_topic_counts[session_id][topic_id] += 1
        speaker_topic_counts[speaker][topic_id] += 1
        overall_topic_counts[topic_id] += 1

    total_docs = len(doc_topic_data) or 1
    overall_topics = [
        {
            "topic_id": tid,
            "topic_share": count / total_docs,
            "top_terms": topic_terms.get(tid, ""),
        }
        for tid, count in overall_topic_counts.items()
        if tid != -1
    ]

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

    # Pooled view for group charts; empty / all-outlier → no chart specs.
    bertopic_pooled = {
        "schema_version": SCHEMA_VERSION,
        "all_outlier": bool(meta.get("all_outlier")),
        "topics": [
            {
                "topic_id": row["topic_id"],
                "topic_share": float(row["topic_share"]),
                "top_terms": row.get("top_terms", ""),
            }
            for row in sorted(overall_topics, key=lambda r: -r["topic_share"])
        ],
    }

    return {
        "session_rows": canonical_session_rows,
        "speaker_rows": canonical_speaker_rows,
        "bertopic_pooled": bertopic_pooled,
        "meta": meta,
    }
