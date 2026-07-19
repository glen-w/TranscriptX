"""Validate and normalize authoritative collect payloads."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from transcriptx.core.analysis.group_llm_synthesis import errors as err
from transcriptx.core.analysis.group_llm_synthesis.schemas import (
    COLLECT_BLOB_AGGREGATION_KEY,
    COLLECT_SCHEMA_VERSION,
    METADATA_SAMPLE_K,
)
from transcriptx.core.analysis.group_llm_synthesis.speakers import (
    build_artifact_tokens,
    resolve_speaker_canonical_id,
)


@dataclass
class NormalizedSession:
    transcript_id: str
    transcript_id_synthetic: bool
    order_index: int
    encounter_ordinal: int
    summary: str
    member_run_rel: str = ""


@dataclass
class NormalizedSpeakerSession:
    canonical_speaker_id: str
    display_name: str
    transcript_id: str
    transcript_id_synthetic: bool
    order_index: int
    encounter_ordinal: int
    summary: str


@dataclass
class ValidationResult:
    sessions: list[NormalizedSession] = field(default_factory=list)
    speaker_groups: dict[str, list[NormalizedSpeakerSession]] = field(
        default_factory=dict
    )
    artifact_tokens: dict[str, str] = field(default_factory=dict)
    display_names: dict[str, str] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    global_error_code: str | None = None
    global_error_message: str | None = None
    speaker_error_code: str | None = None
    speaker_error_message: str | None = None


def _synthetic_transcript_id(
    *,
    run_id: str,
    member_key: str,
    encounter_ordinal: int,
) -> str:
    raw = f"{run_id}|{member_key}|{encounter_ordinal}"
    return f"synthetic:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_global_collect(
    path: Path | None,
    *,
    run_id: str,
    required: bool,
) -> tuple[list[NormalizedSession], list[dict[str, Any]], str | None, str | None]:
    warnings: list[dict[str, Any]] = []
    if path is None or not path.is_file():
        if required:
            return (
                [],
                warnings,
                err.MISSING_COLLECT_ARTIFACT,
                "llm_summary.json missing",
            )
        return [], warnings, None, None
    try:
        payload = _load_json(path)
    except Exception as exc:
        return [], warnings, err.INVALID_COLLECT_PAYLOAD, str(exc)
    if not isinstance(payload, dict):
        return [], warnings, err.INVALID_COLLECT_PAYLOAD, "collect root must be object"
    schema_version = payload.get("schema_version", COLLECT_SCHEMA_VERSION)
    if schema_version not in (1, "1", COLLECT_SCHEMA_VERSION):
        return [], warnings, err.COLLECT_SCHEMA_MISMATCH, "unsupported schema_version"
    agg_key = payload.get("aggregation_key")
    if agg_key is not None and agg_key != COLLECT_BLOB_AGGREGATION_KEY:
        return [], warnings, err.COLLECT_SCHEMA_MISMATCH, "aggregation_key mismatch"
    summaries = payload.get("summaries")
    if not isinstance(summaries, list):
        return [], warnings, err.INVALID_COLLECT_PAYLOAD, "summaries must be a list"

    sessions: list[NormalizedSession] = []
    seen_orders: set[int] = set()
    for ordinal, entry in enumerate(summaries):
        if not isinstance(entry, dict):
            warnings.append({"code": err.INVALID_COLLECT_PAYLOAD, "ordinal": ordinal})
            continue
        summary = entry.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            warnings.append({"code": err.INVALID_COLLECT_PAYLOAD, "ordinal": ordinal})
            continue
        order_raw = entry.get("order_index")
        try:
            order_index = int(order_raw) if order_raw is not None else 10**9 + ordinal
        except (TypeError, ValueError):
            order_index = 10**9 + ordinal
        if order_index in seen_orders:
            warnings.append(
                {"code": err.DUPLICATE_ORDER_INDEX, "order_index": order_index}
            )
        seen_orders.add(order_index)
        tid = str(entry.get("source_transcript_id") or "").strip()
        synthetic = False
        member_key = str(
            entry.get("source_transcript_id")
            or entry.get("member_run_rel")
            or f"row-{ordinal}"
        )
        if not tid:
            tid = _synthetic_transcript_id(
                run_id=run_id, member_key=member_key, encounter_ordinal=ordinal
            )
            synthetic = True
        sessions.append(
            NormalizedSession(
                transcript_id=tid,
                transcript_id_synthetic=synthetic,
                order_index=order_index,
                encounter_ordinal=ordinal,
                summary=summary.strip(),
                member_run_rel=str(entry.get("member_run_rel") or ""),
            )
        )
    sessions.sort(key=lambda s: (s.order_index, s.transcript_id, s.encounter_ordinal))
    if not sessions:
        return (
            [],
            warnings,
            err.NO_USABLE_MEMBER_SUMMARIES,
            "no usable member summaries",
        )
    return sessions, warnings, None, None


def validate_speaker_rows(
    path: Path | None,
    *,
    run_id: str,
    required: bool,
) -> tuple[
    dict[str, list[NormalizedSpeakerSession]],
    dict[str, str],
    dict[str, str],
    list[dict[str, Any]],
    str | None,
    str | None,
]:
    warnings: list[dict[str, Any]] = []
    if path is None or not path.is_file():
        if required:
            return (
                {},
                {},
                {},
                warnings,
                err.MISSING_COLLECT_ARTIFACT,
                "speaker_rows.json missing",
            )
        return {}, {}, {}, warnings, None, None
    try:
        rows = _load_json(path)
    except Exception as exc:
        return {}, {}, {}, warnings, err.INVALID_COLLECT_PAYLOAD, str(exc)
    if not isinstance(rows, list):
        return (
            {},
            {},
            {},
            warnings,
            err.INVALID_COLLECT_PAYLOAD,
            "speaker_rows must be a list",
        )

    groups: dict[str, list[NormalizedSpeakerSession]] = {}
    display_names: dict[str, str] = {}
    for ordinal, entry in enumerate(rows):
        if not isinstance(entry, dict):
            warnings.append({"code": err.INVALID_COLLECT_PAYLOAD, "ordinal": ordinal})
            continue
        if str(entry.get("status") or "") != "success":
            continue
        summary = entry.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            continue
        order_raw = entry.get("order_index")
        try:
            order_index = int(order_raw) if order_raw is not None else 10**9 + ordinal
        except (TypeError, ValueError):
            order_index = 10**9 + ordinal
        tid = str(entry.get("source_transcript_id") or "").strip()
        synthetic = False
        member_key = tid or str(entry.get("speaker_key") or f"row-{ordinal}")
        if not tid:
            tid = _synthetic_transcript_id(
                run_id=run_id, member_key=member_key, encounter_ordinal=ordinal
            )
            synthetic = True
        row_key = entry.get("speaker_key") or entry.get("display_name") or ordinal
        canon, display = resolve_speaker_canonical_id(
            canonical_speaker_id=(
                str(entry.get("canonical_speaker_id"))
                if entry.get("canonical_speaker_id") is not None
                else None
            ),
            raw_or_display=str(entry.get("display_name") or entry.get("speaker") or ""),
            source_transcript_id=tid,
            row_key_or_ordinal=row_key,
        )
        sess = NormalizedSpeakerSession(
            canonical_speaker_id=canon,
            display_name=display,
            transcript_id=tid,
            transcript_id_synthetic=synthetic,
            order_index=order_index,
            encounter_ordinal=ordinal,
            summary=summary.strip(),
        )
        groups.setdefault(canon, []).append(sess)
        display_names[canon] = display

    for canon in groups:
        groups[canon].sort(
            key=lambda s: (s.order_index, s.transcript_id, s.encounter_ordinal)
        )

    if not groups:
        return (
            {},
            {},
            {},
            warnings,
            err.NO_USABLE_MEMBER_SUMMARIES,
            "no usable speaker rows",
        )

    canon_ids = sorted(groups.keys())
    tokens = build_artifact_tokens(canon_ids, [display_names[c] for c in canon_ids])
    return groups, tokens, display_names, warnings, None, None


def cap_warning_samples(
    warnings: list[dict[str, Any]], k: int = METADATA_SAMPLE_K
) -> list[dict[str, Any]]:
    return warnings[:k]
