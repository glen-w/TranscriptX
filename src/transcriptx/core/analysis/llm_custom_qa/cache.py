"""Cache lookup helpers for llm_custom_qa (validate-before-reuse)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from transcriptx.core.analysis.llm_custom_qa.artifact_schema import validate_artifact
from transcriptx.core.analysis.llm_custom_qa.errors import (
    CustomQAError,
    CustomQAFailureCode,
)
from transcriptx.core.analysis.llm_custom_qa.versioning import (
    CONTRACT_VERSION,
    MODULE_VERSION,
    SCHEMA_ID,
)
from transcriptx.core.analysis.llm_support.hashing import sha256_canonical_json


def try_load_cached_artifact(
    json_final: Path,
    *,
    cache_key: str,
    questions_requested: list[str],
    questions_hash: str,
) -> Optional[dict[str, Any]]:
    """Return validated cached artifact if present and matching, else None.

    On schema/invariant failure raises CUSTOM_QA_CACHE_INVALID so callers can
    regenerate once.
    """
    if not json_final.exists():
        return None
    try:
        raw = json.loads(json_final.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    if raw.get("cache_key") != cache_key:
        return None
    try:
        return validate_artifact(
            raw,
            questions_requested=questions_requested,
            questions_hash=questions_hash,
        )
    except Exception as exc:
        raise CustomQAError(
            f"Cached artifact failed validation: {exc}",
            code=CustomQAFailureCode.CUSTOM_QA_CACHE_INVALID,
            error_context={"path": str(json_final)},
        ) from exc


def try_load_cached_structured_artifact(
    path: Path,
    *,
    cache_key: str,
    questions_hash: str,
    question_order: tuple[str, ...] | list[str],
) -> Optional[dict[str, Any]]:
    """Validate-before-reuse for v2 artifacts (authoritative generation or alias)."""
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    if raw.get("cache_key") != cache_key:
        return None
    if raw.get("questions_hash") != questions_hash:
        return None
    if list(raw.get("question_order") or []) != list(question_order):
        return None
    try:
        from transcriptx.core.analysis.llm_custom_qa.structured_contracts import (
            validate_structured_artifact,
        )

        return validate_structured_artifact(raw)
    except Exception as exc:
        raise CustomQAError(
            f"Cached v2 artifact failed validation: {exc}",
            code=CustomQAFailureCode.CUSTOM_QA_CACHE_INVALID,
            error_context={"path": str(path)},
        ) from exc


def build_routing_cache_key(
    *,
    questions_hash: str,
    question_order: tuple[str, ...] | list[str],
    catalog_version: str,
    expanded_pack_ids: tuple[str, ...] | list[str],
    snapshot_fingerprints: dict[str, str],
    include_transcript: bool,
    max_packs_per_question: int,
    router_model: str,
    router_generation_options: dict[str, Any],
    router_prompt_version: str,
) -> str:
    payload = {
        "catalog_version": catalog_version,
        "contract_version": CONTRACT_VERSION,
        "expanded_pack_ids": list(expanded_pack_ids),
        "include_transcript": include_transcript,
        "max_packs_per_question": max_packs_per_question,
        "module_version": MODULE_VERSION,
        "question_order": list(question_order),
        "questions_hash": questions_hash,
        "router_generation_options": dict(sorted(router_generation_options.items())),
        "router_model": router_model,
        "router_prompt_version": router_prompt_version,
        "schema_id": SCHEMA_ID,
        "snapshot_fingerprints": dict(sorted(snapshot_fingerprints.items())),
    }
    return sha256_canonical_json(payload)


def build_answer_cache_key(
    *,
    questions_hash: str,
    question_order: tuple[str, ...] | list[str],
    routes_hash: str,
    speaker_keys: tuple[str, ...] | list[str],
    transcript_global_fingerprint: str,
    transcript_speaker_fingerprints: dict[str, str],
    catalog_version: str,
    scheduler_version: str,
    eligibility_policy_version: str,
    answer_model: str,
    answer_generation_options: dict[str, Any],
    answer_prompt_version: str,
    repair_prompt_version: str,
    rendered_evidence_format_version: str,
    materialiser_versions: dict[str, str],
) -> str:
    payload = {
        "answer_generation_options": dict(sorted(answer_generation_options.items())),
        "answer_model": answer_model,
        "answer_prompt_version": answer_prompt_version,
        "catalog_version": catalog_version,
        "contract_version": CONTRACT_VERSION,
        "eligibility_policy_version": eligibility_policy_version,
        "materialiser_versions": dict(sorted(materialiser_versions.items())),
        "module_version": MODULE_VERSION,
        "question_order": list(question_order),
        "questions_hash": questions_hash,
        "rendered_evidence_format_version": rendered_evidence_format_version,
        "repair_prompt_version": repair_prompt_version,
        "routes_hash": routes_hash,
        "scheduler_version": scheduler_version,
        "schema_id": SCHEMA_ID,
        "speaker_keys": list(speaker_keys),
        "transcript_global_fingerprint": transcript_global_fingerprint,
        "transcript_speaker_fingerprints": dict(
            sorted(transcript_speaker_fingerprints.items())
        ),
    }
    return sha256_canonical_json(payload)
