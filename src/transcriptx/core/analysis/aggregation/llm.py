"""
Group aggregation for LLM analysis modules.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.aggregation.common import extract_payload
from transcriptx.core.analysis.aggregation.rows import (
    _build_display_to_canonical,
    _fallback_canonical_id,
    _session_row_base,
)
from transcriptx.core.analysis.llm_support.action_items_contract import (
    dedupe_action_items,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap
from transcriptx.core.analysis.aggregation.schema import get_transcript_id
from transcriptx.core.analysis.llm_support.filenames import safe_speaker_filename
from transcriptx.core.utils._path_core import get_canonical_base_name


def _artifact_relpath(result: Dict[str, Any], needle: str) -> Optional[str]:
    artifacts = result.get("artifacts") or []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        rel = artifact.get("relative_path") or artifact.get("path")
        if isinstance(rel, str) and needle in rel and rel.endswith(".json"):
            return rel
    return None


def _status_counts(items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def aggregate_llm_summary_blob(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """Collect per-member llm_summary payloads into a group blob."""
    del canonical_speaker_map  # unused; signature matches AggregationFn
    summaries: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = extract_payload(result.module_results, "llm_summary")
        if not payload:
            continue
        entry = dict(payload)
        entry["source_transcript_id"] = get_transcript_id(result, transcript_set)
        entry["order_index"] = result.order_index
        summaries.append(entry)
    if not summaries:
        return None
    summaries.sort(key=lambda row: row.get("order_index", 0))
    return {
        "blob_name": "llm_summary",
        "blob_payload": {
            "schema_version": 1,
            "aggregation_key": "llm_summary",
            "summaries": summaries,
        },
    }


def aggregate_narrative_summary_blob(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """Collect per-member narrative_summary payloads into a group blob."""
    del canonical_speaker_map
    narratives: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = extract_payload(result.module_results, "narrative_summary")
        if not payload:
            continue
        entry = dict(payload)
        entry["source_transcript_id"] = get_transcript_id(result, transcript_set)
        entry["order_index"] = result.order_index
        narratives.append(entry)
    if not narratives:
        return None
    narratives.sort(key=lambda row: row.get("order_index", 0))
    return {
        "blob_name": "narrative_summary",
        "blob_payload": {
            "schema_version": 1,
            "aggregation_key": "narrative_summary",
            "summaries": narratives,
        },
    }


def _load_speaker_summary_payload(
    result: PerTranscriptResult, speaker: str, artifact_stem: str
) -> Dict[str, Any]:
    if not result.output_dir:
        return {}
    base = get_canonical_base_name(result.transcript_path)
    safe = safe_speaker_filename(speaker)
    candidate = (
        Path(result.output_dir)
        / "llm_speaker_summary"
        / "data"
        / "speakers"
        / f"{base}_{safe}_{artifact_stem}.json"
    )
    if not candidate.exists():
        return {}
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def aggregate_llm_speaker_summary_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """Aggregate per-speaker LLM summaries across sessions."""
    session_rows: List[Dict[str, Any]] = []
    speaker_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = extract_payload(result.module_results, "llm_speaker_summary")
        if not payload:
            continue
        speakers = payload.get("speakers") or []
        if not isinstance(speakers, list):
            continue
        transcript_id = get_transcript_id(result, transcript_set)
        session_row = _session_row_base(result, transcript_set)
        session_row["speaker_count"] = len(speakers)
        session_row["success_count"] = sum(
            1
            for entry in speakers
            if isinstance(entry, dict) and entry.get("status") == "success"
        )
        session_rows.append(session_row)
        display_to_canonical = _build_display_to_canonical(
            result.transcript_path, canonical_speaker_map
        )
        for entry in speakers:
            if not isinstance(entry, dict):
                continue
            speaker = str(entry.get("speaker") or "")
            if not speaker:
                continue
            artifact_stem = str(entry.get("artifact_stem") or "llm_speaker_summary")
            summary_payload = _load_speaker_summary_payload(
                result, speaker, artifact_stem
            )
            canonical_id = display_to_canonical.get(
                speaker, _fallback_canonical_id(speaker)
            )
            speaker_rows.append(
                {
                    "canonical_speaker_id": canonical_id,
                    "display_name": canonical_speaker_map.canonical_to_display.get(
                        canonical_id, speaker
                    ),
                    "source_transcript_id": transcript_id,
                    "order_index": result.order_index,
                    "status": entry.get("status"),
                    "summary": summary_payload.get("summary") or "",
                    "speaker_key": entry.get("speaker_key"),
                }
            )
    if not session_rows and not speaker_rows:
        return None
    speaker_rows.sort(
        key=lambda row: (
            row.get("canonical_speaker_id", 0),
            row.get("order_index", 0),
        )
    )
    return {
        "session_rows": session_rows,
        "speaker_rows": speaker_rows,
        "drop_csv_keys": ["summary"],
    }


def aggregate_llm_action_items_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """Concatenate and dedupe action items across group members."""
    del canonical_speaker_map
    session_rows: List[Dict[str, Any]] = []
    action_item_rows: List[Dict[str, Any]] = []
    collected: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = extract_payload(result.module_results, "llm_action_items")
        if not payload:
            continue
        items = payload.get("items") or []
        if not isinstance(items, list):
            continue
        transcript_id = get_transcript_id(result, transcript_set)
        typed_items = [item for item in items if isinstance(item, dict)]
        status_counts = _status_counts(typed_items)
        session_row = _session_row_base(result, transcript_set)
        session_row["item_count"] = len(typed_items)
        for status, count in status_counts.items():
            session_row[f"status_{status}"] = count
        session_rows.append(session_row)
        source_rel = _artifact_relpath(
            result.module_results.get("llm_action_items", {}), "llm_action_items"
        )
        for index, item in enumerate(typed_items):
            enriched = dict(item)
            enriched["_model_index"] = index
            enriched["_source_transcript_id"] = transcript_id
            enriched["_order_index"] = result.order_index
            enriched["_source_run_relpath"] = result.output_dir
            enriched["_source_artifact_relpath"] = source_rel
            collected.append(enriched)

    if not collected:
        return None

    deduped = dedupe_action_items(collected)
    # Group-level ordering: stable by session then original model order.
    deduped.sort(
        key=lambda item: (
            int(item.get("_order_index", 0)),
            int(item.get("_model_index", 0)),
        )
    )
    for item in deduped:
        text = str(item.get("text") or "")
        transcript_id = str(item.get("_source_transcript_id") or "")
        hash_payload = (
            f"{transcript_id}:{text[:200]}:{item.get('owner')}:{item.get('deadline')}"
        )
        action_item_rows.append(
            {
                "id": hashlib.sha1(hash_payload.encode("utf-8")).hexdigest(),
                "order_index": item.get("_order_index", 0),
                "text": text,
                "owner": item.get("owner"),
                "deadline": item.get("deadline"),
                "status": item.get("status"),
                "quote": item.get("quote"),
                "confidence": item.get("confidence"),
                "source_transcript_id": transcript_id,
                "source_run_relpath": item.get("_source_run_relpath"),
                "source_artifact_relpath": item.get("_source_artifact_relpath"),
            }
        )
    return {
        "session_rows": session_rows,
        "speaker_rows": [],
        "content_rows": action_item_rows,
        "content_rows_name": "action_item_rows",
        "metrics_spec": [
            {
                "name": "item_count",
                "format": "int",
                "description": "Action items in session",
            },
            {
                "name": "confidence",
                "format": "float",
                "description": "Action item confidence",
            },
        ],
    }


def aggregate_llm_custom_qa_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """Collect custom-QA answer rows; flag hash/schema mismatches separately."""
    del canonical_speaker_map
    session_rows: List[Dict[str, Any]] = []
    qa_answer_rows: List[Dict[str, Any]] = []
    qa_member_failures: List[Dict[str, Any]] = []
    expected_hash: Optional[str] = None
    expected_schema: Optional[str] = None
    expected_questions: List[str] = []
    expected_resolved_from: Optional[str] = None

    for result in per_transcript_results:
        module_result = result.module_results.get("llm_custom_qa") or {}
        payload = extract_payload(result.module_results, "llm_custom_qa")
        transcript_id = get_transcript_id(result, transcript_set)
        status = str(module_result.get("status") or "")
        if status and status != "success":
            qa_member_failures.append(
                {
                    "source_transcript_id": transcript_id,
                    "order_index": result.order_index,
                    "reason": "module_not_success",
                    "status": status,
                }
            )
            continue
        if not payload:
            qa_member_failures.append(
                {
                    "source_transcript_id": transcript_id,
                    "order_index": result.order_index,
                    "reason": "missing_payload",
                }
            )
            continue

        qhash = payload.get("questions_hash")
        schema_id = payload.get("schema_id")
        if expected_hash is None:
            expected_hash = qhash
            expected_schema = schema_id
            raw_qs = payload.get("questions_requested") or []
            expected_questions = list(raw_qs) if isinstance(raw_qs, list) else []
            expected_resolved_from = (payload.get("provenance") or {}).get(
                "resolved_from"
            )
        elif qhash != expected_hash or schema_id != expected_schema:
            qa_member_failures.append(
                {
                    "source_transcript_id": transcript_id,
                    "order_index": result.order_index,
                    "reason": "hash_or_schema_mismatch",
                    "questions_hash": qhash,
                    "schema_id": schema_id,
                }
            )
            continue

        answers = payload.get("answers") or []
        if not isinstance(answers, list):
            qa_member_failures.append(
                {
                    "source_transcript_id": transcript_id,
                    "order_index": result.order_index,
                    "reason": "invalid_answers",
                }
            )
            continue

        session_row = _session_row_base(result, transcript_set)
        session_row["question_count"] = len(payload.get("questions_requested") or [])
        session_row["outcome"] = payload.get("outcome")
        session_row["questions_hash"] = qhash
        session_row["resolved_from"] = (payload.get("provenance") or {}).get(
            "resolved_from"
        )
        session_rows.append(session_row)

        source_rel = _artifact_relpath(module_result, "llm_custom_qa")
        for answer in answers:
            if not isinstance(answer, dict):
                continue
            qa_answer_rows.append(
                {
                    "order_index": result.order_index,
                    "source_transcript_id": transcript_id,
                    "question_index": answer.get("question_index"),
                    "question": answer.get("question"),
                    "status": answer.get("status"),
                    "answer": answer.get("answer"),
                    "abstain_reason": answer.get("abstain_reason"),
                    "system_reason": answer.get("system_reason"),
                    "confidence": answer.get("confidence"),
                    "citations": answer.get("citations") or [],
                    "questions_hash": qhash,
                    "resolved_from": (payload.get("provenance") or {}).get(
                        "resolved_from"
                    ),
                    "artifact_path": source_rel,
                    "source_run_relpath": result.output_dir,
                }
            )

    if not session_rows and not qa_member_failures:
        return None

    extra_tables = {"qa_member_failures": qa_member_failures}
    return {
        "session_rows": session_rows,
        "speaker_rows": [],
        "content_rows": qa_answer_rows,
        "content_rows_name": "qa_answer_rows",
        "extra_tables": extra_tables,
        "metrics_spec": [
            {
                "name": "question_count",
                "format": "int",
                "description": "Questions requested in session",
            },
        ],
        "group_metadata": {
            "questions_hash": expected_hash,
            "questions_requested": expected_questions,
            "resolved_from": expected_resolved_from,
        },
    }
