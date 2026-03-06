"""
Shared schema and validation for group aggregation outputs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List, Tuple, TypedDict, Union

from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult

TranscriptId = Union[str, int]
SpeakerId = Union[str, int]


class MetricSpec(TypedDict, total=False):
    name: str
    unit: str
    description: str
    format: str


class SessionRow(TypedDict, total=False):
    transcript_id: TranscriptId
    order_index: int
    run_relpath: str
    session_label: str


class SpeakerRow(TypedDict, total=False):
    canonical_speaker_id: SpeakerId
    display_name: str
    speaker_key: str


def _stable_hash(payload: str, prefix: str = "txid_v1_") -> str:
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{prefix}{digest}"


def get_transcript_id(
    result: PerTranscriptResult, transcript_set: TranscriptSet
) -> TranscriptId:
    """
    Resolve transcript_id for group aggregation rows.

    Preference order:
    1) transcript_set.metadata["transcript_id_map"][transcript_path]
    2) transcript_set.metadata["transcript_key_map"][transcript_key]
    3) result.transcript_key (if present)
    4) deterministic versioned hash of transcript_path
    """
    metadata = transcript_set.metadata or {}
    id_map = metadata.get("transcript_id_map") or {}
    if isinstance(id_map, dict):
        resolved = id_map.get(result.transcript_path)
        if resolved is not None:
            return resolved

    key_map = metadata.get("transcript_key_map") or {}
    if isinstance(key_map, dict) and result.transcript_key:
        resolved = key_map.get(result.transcript_key)
        if resolved is not None:
            return resolved

    if result.transcript_key:
        return result.transcript_key

    return _stable_hash(result.transcript_path)


def validate_session_rows(
    rows: Iterable[Dict[str, Any]],
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validate required keys/types for session rows.
    Returns (ok, errors).
    """
    errors: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows):
        missing = []
        if "transcript_id" not in row:
            missing.append("transcript_id")
        if "order_index" not in row:
            missing.append("order_index")
        if missing:
            errors.append({"row_index": idx, "missing_keys": missing})
            continue
        if not isinstance(row.get("order_index"), int):
            errors.append(
                {
                    "row_index": idx,
                    "invalid_keys": {
                        "order_index": type(row.get("order_index")).__name__
                    },
                }
            )
        transcript_id = row.get("transcript_id")
        if not isinstance(transcript_id, (str, int)):
            errors.append(
                {
                    "row_index": idx,
                    "invalid_keys": {"transcript_id": type(transcript_id).__name__},
                }
            )
    return (len(errors) == 0, errors)


def validate_speaker_rows(
    rows: Iterable[Dict[str, Any]],
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validate required keys/types for speaker rows.
    Returns (ok, errors).
    """
    errors: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows):
        missing = []
        if "canonical_speaker_id" not in row:
            missing.append("canonical_speaker_id")
        if missing:
            errors.append({"row_index": idx, "missing_keys": missing})
            continue
        speaker_id = row.get("canonical_speaker_id")
        if not isinstance(speaker_id, (str, int)):
            errors.append(
                {
                    "row_index": idx,
                    "invalid_keys": {"canonical_speaker_id": type(speaker_id).__name__},
                }
            )
    return (len(errors) == 0, errors)


def serialize_value(value: Any) -> Any:
    """
    Normalize row values for CSV export.
    """
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    return str(value)
