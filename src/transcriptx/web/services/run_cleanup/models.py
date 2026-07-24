"""Immutable models and constants for bulk run cleanup."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

CLEANUP_POLICY_VERSION = 7
JOURNAL_SCHEMA_VERSION = 1
CLEANUP_RESULT_SCHEMA_VERSION = 1
STAGING_DIR_NAME = ".cleanup_staging"
CONFIRM_DELETE_ALL = "DELETE ALL"
CONFIRM_DELETE_OLD = "DELETE OLD RUNS"
CLEANUP_BUSY = "CLEANUP_BUSY"
PLATFORM_UNSUPPORTED = "PLATFORM_UNSUPPORTED"
HANDLE_STORE_FULL = "HANDLE_STORE_FULL"
# New operations only — recovery of larger schema-3 journals stays allowed.
MAX_CLEANUP_CANDIDATES = 2048
FD_BUDGET_SAFETY_RESERVE = 64


class CleanupMode(str, Enum):
    DELETE_ALL = "DELETE_ALL"
    DELETE_OLD = "DELETE_OLD"


class CleanupStatus(str, Enum):
    NOOP = "NOOP"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED_BEFORE_MUTATION = "FAILED_BEFORE_MUTATION"
    STALE_PLAN = "STALE_PLAN"
    BLOCKED = "BLOCKED"
    ALREADY_EXECUTED = "ALREADY_EXECUTED"


class TargetStatus(str, Enum):
    """User-facing target outcomes on CleanupTargetResult.

    Mid-flight durable journal states use snake_case strings in the operation
    journal (``staging_started``, ``physical_delete_verified``, …) and are
    *not* assigned as ``CleanupTargetResult.status``. The members below marked
    legacy remain for deserialization / session-clear compatibility only.
    """

    VISIBLE_REMOVED = "VISIBLE_REMOVED"
    PHYSICAL_DELETED = "PHYSICAL_DELETED"
    LOCKED_SKIP = "LOCKED_SKIP"
    SUBJECT_LOCKED_SKIP = "SUBJECT_LOCKED_SKIP"
    STALE = "STALE"
    EXTERNAL_DISAPPEARED = "EXTERNAL_DISAPPEARED"
    STAGING_FAILED = "STAGING_FAILED"
    STAGING_STARTED = "STAGING_STARTED"  # legacy / unused on results
    STAGED_JOURNAL_INCOMPLETE = "STAGED_JOURNAL_INCOMPLETE"
    STAGED_IDENTITY_UNVERIFIED = "STAGED_IDENTITY_UNVERIFIED"
    PHYSICAL_DELETE_VERIFIED = "PHYSICAL_DELETE_VERIFIED"  # legacy / unused on results
    PHYSICAL_DELETE_FAILED = "PHYSICAL_DELETE_FAILED"
    PHYSICAL_DELETE_REFUSED = "PHYSICAL_DELETE_REFUSED"
    PHYSICAL_DELETE_PARTIAL = "PHYSICAL_DELETE_PARTIAL"
    INTERRUPTED_STAGING = "INTERRUPTED_STAGING"  # session-clear visibility only
    PARENT_PRUNE_WARNING = "PARENT_PRUNE_WARNING"
    INVALIDATION_WARNING = "INVALIDATION_WARNING"
    SKIPPED = "SKIPPED"
    RETAINED = "RETAINED"


class EntryClassification(str, Enum):
    eligible = "eligible"
    invalid = "invalid"
    unknown = "unknown"
    staging = "staging"
    symlink = "symlink"
    mount = "mount"
    cross_device = "cross_device"
    unreadable = "unreadable"
    protected = "protected"


class SubjectType(str, Enum):
    transcript = "transcript"
    group = "group"


@dataclass(frozen=True)
class RootIdentity:
    kind: SubjectType
    configured_path: str
    canonical_path: str
    dev: int | None
    ino: int | None
    is_symlink: bool
    exists: bool = True


@dataclass(frozen=True)
class TargetIdentity:
    """Stable identity used for journal matching and staging basename inputs."""

    subject_type: SubjectType
    subject_id: str
    run_id: str
    root_relative_path: str
    canonical_path: str


@dataclass(frozen=True)
class TargetSnapshot:
    """Identity plus staleness-sensitive filesystem fields."""

    identity: TargetIdentity
    filesystem_dev: int
    filesystem_ino: int
    tree_fingerprint: str
    safety_status: EntryClassification
    mtime_ns: int = 0
    size_estimate_bytes: int = 0
    file_count: int = 0


@dataclass(frozen=True)
class CleanupTarget:
    subject_type: SubjectType
    subject_id: str
    run_id: str
    root_relative_path: str
    canonical_path: str
    mtime_ns: int
    filesystem_dev: int
    filesystem_ino: int
    size_estimate_bytes: int
    file_count: int
    tree_fingerprint: str
    safety_status: EntryClassification

    def identity(self) -> TargetIdentity:
        return TargetIdentity(
            subject_type=self.subject_type,
            subject_id=self.subject_id,
            run_id=self.run_id,
            root_relative_path=self.root_relative_path,
            canonical_path=self.canonical_path,
        )

    def snapshot(self) -> TargetSnapshot:
        return TargetSnapshot(
            identity=self.identity(),
            filesystem_dev=self.filesystem_dev,
            filesystem_ino=self.filesystem_ino,
            tree_fingerprint=self.tree_fingerprint,
            safety_status=self.safety_status,
            mtime_ns=self.mtime_ns,
            size_estimate_bytes=self.size_estimate_bytes,
            file_count=self.file_count,
        )


@dataclass(frozen=True)
class CleanupExclusion:
    path_relative: str
    classification: EntryClassification
    reason: str
    root_kind: SubjectType | None = None


@dataclass(frozen=True)
class CleanupPlan:
    plan_id: str
    mode: CleanupMode
    policy_version: int
    created_at_iso: str
    roots: tuple[RootIdentity, ...]
    candidates: tuple[CleanupTarget, ...]
    retained: tuple[CleanupTarget, ...]
    exclusions: tuple[CleanupExclusion, ...]
    warnings: tuple[str, ...]
    blocking_errors: tuple[str, ...]
    can_execute: bool
    # Bound into plan_id (policy ≥ 7); defaults keep older test constructors valid.
    classifier_version: int = 1
    newest_run_policy_version: int = 1

    def __post_init__(self) -> None:
        kinds = [r.kind for r in self.roots]
        if len(kinds) != len(set(kinds)):
            raise ValueError("CleanupPlan roots must have unique kinds")
        ids = [
            (t.subject_type, t.subject_id, t.run_id, t.canonical_path)
            for t in (*self.candidates, *self.retained)
        ]
        if len(ids) != len(set(ids)):
            raise ValueError("CleanupPlan target identities must be unique")
        for t in (*self.candidates, *self.retained):
            if t.filesystem_dev <= 0 or t.filesystem_ino <= 0:
                raise ValueError("target filesystem identity must be positive")
            if not t.canonical_path or not Path(t.canonical_path).is_absolute():
                # Allow non-absolute only when empty sentinel rows are absent;
                # production targets always use absolute canonicals.
                if t.canonical_path:
                    raise ValueError("target canonical_path must be absolute")
            parts = Path(t.root_relative_path).parts
            if t.root_relative_path and len(parts) != 2:
                raise ValueError(
                    "target root_relative_path must have exactly two components"
                )
            if len(t.tree_fingerprint) != 64:
                raise ValueError("target tree_fingerprint must be 64 hex chars")


@dataclass(frozen=True)
class CleanupPreview:
    plan_id: str
    mode: CleanupMode
    can_execute: bool
    transcript_subjects: int
    group_subjects: int
    run_count: int
    file_count: int
    size_estimate_bytes: int
    candidates: tuple[dict[str, Any], ...]
    retained: tuple[dict[str, Any], ...]
    exclusions: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    blocking_errors: tuple[str, ...]


@dataclass(frozen=True)
class CleanupAuthorization:
    acknowledged: bool
    phrase: str
    mode: CleanupMode
    plan_id: str


@dataclass(frozen=True)
class CleanupTargetResult:
    subject_type: SubjectType
    subject_id: str
    run_id: str
    root_relative_path: str
    canonical_path: str
    status: TargetStatus
    message: str = ""
    staging_path: str | None = None
    filesystem_dev: int | None = None
    filesystem_ino: int | None = None
    # Legacy duplicate of subject_type; omitted from new serializations
    # (CLEANUP_RESULT_SCHEMA_VERSION >= 1). Still accepted on read.
    root_kind: SubjectType | None = None


@dataclass(frozen=True)
class CleanupResult:
    operation_id: str
    plan_id: str
    mode: CleanupMode
    status: CleanupStatus
    targets: tuple[CleanupTargetResult, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    visible_removed_count: int = 0
    physically_deleted_count: int = 0


@dataclass(frozen=True)
class StageOutcome:
    """Structured result of one staging attempt with enforced invariants."""

    target: CleanupTarget
    staging_path: str | None
    rename_attempted: bool
    visible_removed: bool
    staged_dev: int | None
    staged_ino: int | None
    journal_updated: bool
    deletion_ready: bool
    target_result: CleanupTargetResult
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.visible_removed and not self.rename_attempted:
            raise ValueError("visible_removed requires rename_attempted")
        if (self.staged_dev is None) ^ (self.staged_ino is None):
            raise ValueError(
                "staged_dev and staged_ino must both be set or both absent"
            )
        status = self.target_result.status
        if status is TargetStatus.STAGING_FAILED and self.visible_removed:
            raise ValueError("STAGING_FAILED cannot be visible_removed")
        if (
            status is TargetStatus.STAGED_IDENTITY_UNVERIFIED
            and not self.visible_removed
        ):
            raise ValueError("STAGED_IDENTITY_UNVERIFIED requires visible_removed")
        if (
            status is TargetStatus.STAGED_JOURNAL_INCOMPLETE
            and not self.visible_removed
        ):
            raise ValueError("STAGED_JOURNAL_INCOMPLETE requires visible_removed")
        if self.deletion_ready and not self.visible_removed:
            raise ValueError("deletion_ready requires visible_removed")
        if self.deletion_ready and not self.journal_updated:
            raise ValueError("deletion_ready requires journal_updated")
        if self.deletion_ready and (self.staged_dev is None or self.staged_ino is None):
            raise ValueError("deletion_ready requires staged identity")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _target_identity_payload(target: CleanupTarget) -> dict[str, Any]:
    snap = target.snapshot()
    ident = snap.identity
    return {
        "subject_type": ident.subject_type.value,
        "subject_id": ident.subject_id,
        "run_id": ident.run_id,
        "root_relative_path": ident.root_relative_path,
        "canonical_path": ident.canonical_path,
        "filesystem_dev": snap.filesystem_dev,
        "filesystem_ino": snap.filesystem_ino,
        "tree_fingerprint": snap.tree_fingerprint,
        "safety_status": snap.safety_status.value,
    }


def _exclusion_payload(exclusion: CleanupExclusion) -> dict[str, Any]:
    return {
        "path_relative": exclusion.path_relative,
        "classification": exclusion.classification.value,
        "reason": exclusion.reason,
        "root_kind": (
            exclusion.root_kind.value if exclusion.root_kind is not None else None
        ),
    }


def _root_payload(root: RootIdentity) -> dict[str, Any]:
    return {
        "kind": root.kind.value,
        "configured_path": root.configured_path,
        "canonical_path": root.canonical_path,
        "dev": root.dev,
        "ino": root.ino,
        "is_symlink": root.is_symlink,
        "exists": getattr(root, "exists", True),
    }


def compute_plan_id(
    *,
    mode: CleanupMode,
    policy_version: int,
    roots: Sequence[RootIdentity],
    candidates: Sequence[CleanupTarget],
    retained: Sequence[CleanupTarget],
    exclusions: Sequence[CleanupExclusion],
    classifier_version: int = 1,
    newest_run_policy_version: int = 1,
) -> str:
    """Stable sha256 plan id bound to mode, policy, classifier, newest-run, roots."""
    payload = {
        "mode": mode.value,
        "policy_version": policy_version,
        "classifier_version": classifier_version,
        "newest_run_policy_version": newest_run_policy_version,
        "roots": [_root_payload(r) for r in roots],
        "candidates": [_target_identity_payload(t) for t in candidates],
        "retained": [_target_identity_payload(t) for t in retained],
        "exclusions": [_exclusion_payload(e) for e in exclusions],
    }
    digest = hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()
    return digest


def target_to_preview_dict(target: CleanupTarget) -> dict[str, Any]:
    """Root-relative display dict for CleanupPreview (no absolute path)."""
    return {
        "subject_type": target.subject_type.value,
        "subject_id": target.subject_id,
        "run_id": target.run_id,
        "root_relative_path": target.root_relative_path,
        "mtime_ns": target.mtime_ns,
        "size_estimate_bytes": target.size_estimate_bytes,
        "file_count": target.file_count,
        "tree_fingerprint": target.tree_fingerprint,
        "safety_status": target.safety_status.value,
    }


def plan_to_preview(plan: CleanupPlan) -> CleanupPreview:
    transcript_subjects = {
        t.subject_id
        for t in plan.candidates
        if t.subject_type is SubjectType.transcript
    }
    group_subjects = {
        t.subject_id for t in plan.candidates if t.subject_type is SubjectType.group
    }
    exclusion_dicts = tuple(
        {
            "path_relative": e.path_relative,
            "classification": e.classification.value,
            "reason": e.reason,
            "root_kind": e.root_kind.value if e.root_kind is not None else None,
        }
        for e in plan.exclusions
    )
    return CleanupPreview(
        plan_id=plan.plan_id,
        mode=plan.mode,
        can_execute=plan.can_execute,
        transcript_subjects=len(transcript_subjects),
        group_subjects=len(group_subjects),
        run_count=len(plan.candidates),
        file_count=sum(t.file_count for t in plan.candidates),
        size_estimate_bytes=sum(t.size_estimate_bytes for t in plan.candidates),
        candidates=tuple(target_to_preview_dict(t) for t in plan.candidates),
        retained=tuple(target_to_preview_dict(t) for t in plan.retained),
        exclusions=exclusion_dicts,
        warnings=plan.warnings,
        blocking_errors=plan.blocking_errors,
    )


def confirm_phrase_for_mode(mode: CleanupMode) -> str:
    if mode is CleanupMode.DELETE_ALL:
        return CONFIRM_DELETE_ALL
    if mode is CleanupMode.DELETE_OLD:
        return CONFIRM_DELETE_OLD
    raise ValueError(f"Unsupported cleanup mode: {mode!r}")


def authorization_is_valid(
    authorization: CleanupAuthorization,
    *,
    expected_mode: CleanupMode,
    expected_plan_id: str,
) -> bool:
    """Exact phrase match (no trim), acknowledgement, mode, and plan_id."""
    if not authorization.acknowledged:
        return False
    if authorization.mode is not expected_mode:
        return False
    if authorization.plan_id != expected_plan_id:
        return False
    return authorization.phrase == confirm_phrase_for_mode(expected_mode)


def result_as_dict(result: CleanupResult) -> dict[str, Any]:
    """Serialize CleanupResult for journal / handle storage.

    Epoch-1 omits legacy ``root_kind`` (duplicate of ``subject_type``).
    """
    payload = asdict(result)
    payload["cleanup_result_schema_version"] = CLEANUP_RESULT_SCHEMA_VERSION
    for t in payload.get("targets", []):
        if isinstance(t, dict):
            t.pop("root_kind", None)
    return payload


def _target_result_from_mapping(t: Mapping[str, Any]) -> CleanupTargetResult:
    """Epoch-1 target reader."""
    fs_dev = t.get("filesystem_dev")
    fs_ino = t.get("filesystem_ino")
    return CleanupTargetResult(
        subject_type=SubjectType(t["subject_type"]),
        subject_id=str(t["subject_id"]),
        run_id=str(t["run_id"]),
        root_relative_path=str(t["root_relative_path"]),
        canonical_path=str(t["canonical_path"]),
        status=TargetStatus(t["status"]),
        message=str(t.get("message") or ""),
        staging_path=t.get("staging_path"),
        filesystem_dev=int(fs_dev) if fs_dev is not None else None,
        filesystem_ino=int(fs_ino) if fs_ino is not None else None,
        root_kind=None,
    )


def result_from_mapping(data: Mapping[str, Any]) -> CleanupResult:
    """Deserialize CleanupResult; epoch-1 only."""
    version = int(data.get("cleanup_result_schema_version") or CLEANUP_RESULT_SCHEMA_VERSION)
    if version != CLEANUP_RESULT_SCHEMA_VERSION:
        raise ValueError(f"unsupported cleanup_result_schema_version: {version}")
    targets = tuple(_target_result_from_mapping(t) for t in data.get("targets", ()))
    return CleanupResult(
        operation_id=str(data["operation_id"]),
        plan_id=str(data["plan_id"]),
        mode=CleanupMode(data["mode"]),
        status=CleanupStatus(data["status"]),
        targets=targets,
        warnings=tuple(str(w) for w in data.get("warnings", ())),
        errors=tuple(str(e) for e in data.get("errors", ())),
        visible_removed_count=int(data.get("visible_removed_count") or 0),
        physically_deleted_count=int(data.get("physically_deleted_count") or 0),
    )
