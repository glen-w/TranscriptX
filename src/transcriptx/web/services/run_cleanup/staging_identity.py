"""Neutral staging-path and operation-id helpers (no journal↔staging cycle).

Phase A extract: both ``journal`` and ``staging`` import from here instead of
each other for operation-id validation and collision-proof staging paths.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from transcriptx.web.services.run_cleanup.models import (
    STAGING_DIR_NAME,
    CleanupTarget,
    SubjectType,
)

OPERATION_ID_RE = re.compile(r"^[0-9]+_[0-9a-f]{12}$")


def validate_operation_id(operation_id: str) -> str:
    if not isinstance(operation_id, str) or not OPERATION_ID_RE.fullmatch(operation_id):
        raise ValueError(f"invalid operation_id: {operation_id!r}")
    if ".." in operation_id or "/" in operation_id or "\\" in operation_id:
        raise ValueError(f"invalid operation_id: {operation_id!r}")
    return operation_id


def collision_proof_staging_basename(
    target: CleanupTarget, *, root_kind: SubjectType | None = None
) -> str:
    """Basename including root kind, subject, run, and TargetIdentity digest."""
    kind = root_kind or target.subject_type
    identity = (
        f"{kind.value}|{target.subject_type.value}|{target.subject_id}|{target.run_id}|"
        f"{target.canonical_path}|{target.filesystem_dev}|{target.filesystem_ino}|"
        f"{target.tree_fingerprint}"
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    sid = target.subject_id.replace("/", "_").replace("\\", "_")
    return (
        f"{kind.value}__{target.subject_type.value}__"
        f"{sid}__{target.run_id}__{digest}"
    )


def intended_staging_path(
    output_root: Path,
    operation_id: str,
    target: CleanupTarget,
) -> Path:
    operation_id = validate_operation_id(operation_id)
    name = collision_proof_staging_basename(target)
    return Path(output_root) / STAGING_DIR_NAME / operation_id / name
