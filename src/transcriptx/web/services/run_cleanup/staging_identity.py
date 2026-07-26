"""Neutral staging-path and operation-id helpers (no journal↔staging cycle).

Phase A extract: both ``journal`` and ``staging`` import from here instead of
each other for operation-id validation and collision-proof staging paths.

Phase B0: schema-3 basename/path algorithms are frozen under explicit names;
``staging_path_for_journal_schema`` dispatches recovery derivation by journal
schema so future basename changes cannot strand schema-3 trees.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from transcriptx.web.services.run_cleanup.models import (
    JOURNAL_SCHEMA_VERSION,
    READABLE_JOURNAL_SCHEMA_VERSIONS,
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


def collision_proof_staging_basename_schema_3(
    target: CleanupTarget, *, root_kind: SubjectType | None = None
) -> str:
    """Frozen schema-3 basename (root kind + TargetSnapshot identity digest)."""
    kind = root_kind or target.subject_type
    snap = target.snapshot()
    ident = snap.identity
    # Byte-stable with pre-migration string: kind|subject|id|run|canon|dev|ino|fp
    identity = (
        f"{kind.value}|{ident.subject_type.value}|{ident.subject_id}|{ident.run_id}|"
        f"{ident.canonical_path}|{snap.filesystem_dev}|{snap.filesystem_ino}|"
        f"{snap.tree_fingerprint}"
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    sid = ident.subject_id.replace("/", "_").replace("\\", "_")
    return (
        f"{kind.value}__{ident.subject_type.value}__" f"{sid}__{ident.run_id}__{digest}"
    )


# Public alias: current writers use schema-3 algorithm.
collision_proof_staging_basename = collision_proof_staging_basename_schema_3


def intended_staging_path_schema_3(
    output_root: Path,
    operation_id: str,
    target: CleanupTarget,
) -> Path:
    """Frozen schema-3 intended staging path."""
    operation_id = validate_operation_id(operation_id)
    name = collision_proof_staging_basename_schema_3(target)
    return Path(output_root) / STAGING_DIR_NAME / operation_id / name


intended_staging_path = intended_staging_path_schema_3


def staging_path_for_journal_schema(
    schema_version: int,
    output_root: Path,
    operation_id: str,
    target: CleanupTarget,
) -> Path:
    """Derive staging path with the algorithm frozen for ``schema_version``."""
    # Schema 1 and legacy pre-epoch 3 share the same basename/path algorithm.
    if schema_version in READABLE_JOURNAL_SCHEMA_VERSIONS:
        return intended_staging_path_schema_3(output_root, operation_id, target)
    raise ValueError(
        f"unsupported journal schema for staging derivation: {schema_version}"
    )


def resolve_staging_path_for_recovery(
    *,
    output_root: Path,
    operation_id: str,
    target: CleanupTarget,
    journal_schema_version: int = JOURNAL_SCHEMA_VERSION,
    stored_staging_path: str | None = None,
) -> Path:
    """Prefer durable journal staging_path; else schema-dispatched derivation."""
    if stored_staging_path:
        text = str(stored_staging_path).strip()
        if text:
            return Path(text)
    return staging_path_for_journal_schema(
        journal_schema_version, output_root, operation_id, target
    )
