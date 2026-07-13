"""
Group aggregation for semantic similarity modules (legacy + advanced + v2).
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

from transcriptx.core.analysis.aggregation.common import extract_payload
from transcriptx.core.analysis.aggregation.rows import _session_row_base
from transcriptx.core.analysis.aggregation.schema import get_transcript_id
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap

_SEMANTIC_MODULE_PREFERENCE = (
    "semantic_similarity_v2",
    "semantic_similarity_advanced",
    "semantic_similarity",
)


def _pick_semantic_payload(
    module_results: Dict[str, Any],
) -> Tuple[Optional[str], Dict[str, Any]]:
    for module_id in _SEMANTIC_MODULE_PREFERENCE:
        if module_id not in module_results:
            continue
        payload = extract_payload(module_results, module_id)
        if payload:
            return module_id, payload
    return None, {}


def _summary_scalars(payload: Dict[str, Any]) -> Dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    total = payload.get("total_repetitions")
    if total is None:
        total = summary.get("total_repetitions")
    unique = payload.get("unique_patterns")
    if unique is None:
        unique = summary.get("unique_patterns")
    if total is None:
        speaker_reps = payload.get("speaker_repetitions") or {}
        cross = payload.get("cross_speaker_repetitions") or []
        self_count = (
            sum(len(v) for v in speaker_reps.values() if isinstance(v, list))
            if isinstance(speaker_reps, dict)
            else 0
        )
        cross_count = len(cross) if isinstance(cross, list) else 0
        total = self_count + cross_count
    return {
        "total_repetitions": int(total or 0),
        "unique_patterns": int(unique or 0),
        "mode": payload.get("mode"),
        "skipped": bool(payload.get("skipped")),
    }


def _flatten_repetitions(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    speaker_reps = payload.get("speaker_repetitions") or {}
    if isinstance(speaker_reps, dict):
        for speaker, reps in speaker_reps.items():
            if not isinstance(reps, list):
                continue
            for rep in reps:
                if isinstance(rep, dict):
                    rows.append(
                        {**rep, "kind": rep.get("type") or "self", "speaker": speaker}
                    )
    cross = payload.get("cross_speaker_repetitions") or []
    if isinstance(cross, list):
        for rep in cross:
            if isinstance(rep, dict):
                rows.append({**rep, "kind": rep.get("type") or "cross"})
    return rows


def _segment_field(seg: Any, key: str) -> Any:
    if isinstance(seg, dict):
        return seg.get(key)
    return None


def aggregate_semantic_similarity_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """
    Aggregate semantic similarity session scalars and repetition content rows.

    Does not pool embeddings across sessions. Prefer v2 payload when multiple
    semantic modules ran on the same member.
    """
    del canonical_speaker_map
    session_rows: List[Dict[str, Any]] = []
    repetition_rows: List[Dict[str, Any]] = []

    for result in per_transcript_results:
        module_id, payload = _pick_semantic_payload(result.module_results)
        if not module_id or not payload:
            continue
        transcript_id = get_transcript_id(result, transcript_set)
        scalars = _summary_scalars(payload)
        session_row = _session_row_base(result, transcript_set)
        session_row.update(scalars)
        session_row["semantic_module"] = module_id
        session_rows.append(session_row)

        for rep in _flatten_repetitions(payload):
            seg1 = rep.get("segment1")
            seg2 = rep.get("segment2")
            text1 = str(_segment_field(seg1, "text") or "")
            text2 = str(_segment_field(seg2, "text") or "")
            speaker1 = _segment_field(seg1, "speaker") or rep.get("speaker")
            speaker2 = _segment_field(seg2, "speaker")
            similarity = rep.get("similarity")
            kind = str(rep.get("kind") or "unknown")
            hash_payload = (
                f"{transcript_id}:{kind}:{speaker1}:{speaker2}:"
                f"{text1[:120]}:{text2[:120]}"
            )
            repetition_rows.append(
                {
                    "id": hashlib.sha1(hash_payload.encode("utf-8")).hexdigest(),
                    "order_index": result.order_index,
                    "kind": kind,
                    "similarity": similarity,
                    "speaker": speaker1,
                    "speaker_2": speaker2,
                    "text": text1,
                    "text_2": text2,
                    "source_transcript_id": transcript_id,
                    "source_run_relpath": result.output_dir,
                    "semantic_module": module_id,
                }
            )

    if not session_rows:
        return None
    repetition_rows.sort(
        key=lambda row: (
            row.get("order_index", 0),
            -(float(row.get("similarity") or 0.0)),
        )
    )
    return {
        "session_rows": session_rows,
        "speaker_rows": [],
        "content_rows": repetition_rows,
        "content_rows_name": "repetition_rows",
        "metrics_spec": [
            {
                "name": "total_repetitions",
                "format": "int",
                "description": "Repetition matches in session",
            },
            {
                "name": "unique_patterns",
                "format": "int",
                "description": "Unique repetition patterns / clusters",
            },
            {
                "name": "similarity",
                "format": "float",
                "description": "Pair similarity score",
            },
        ],
        "aggregation_note": (
            "Descriptive concat across sessions; embeddings are not re-pooled."
        ),
    }
