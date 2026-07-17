"""Durable cleanup operation journal under STATE_DIR."""

from __future__ import annotations

import errno
import json
import os
import re
import secrets
import stat
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from transcriptx.core.utils.file_lock import FileLock
from transcriptx.web.services.run_cleanup import fd_ops
from transcriptx.web.services.run_cleanup.models import (
    CLEANUP_POLICY_VERSION,
    JOURNAL_SCHEMA_VERSION,
    STAGING_DIR_NAME,
    CleanupMode,
    CleanupPlan,
    CleanupTarget,
    SubjectType,
)
from transcriptx.web.services.run_cleanup.staging_identity import (
    OPERATION_ID_RE as OPERATION_ID_RE,
    collision_proof_staging_basename as collision_proof_staging_basename,
    intended_staging_path as intended_staging_path,
    validate_operation_id as validate_operation_id,
)

FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_JOURNAL_BYTES = 8 * 1024 * 1024
MAX_TARGETS = 50_000
MAX_PATH_LEN = 4096
ALLOWED_TOP_LEVEL = frozenset(
    {
        "journal_schema_version",
        "cleanup_policy_version",
        "operation_id",
        "plan_id",
        "mode",
        "policy_version",
        "created_at",
        "updated_at",
        "roots",
        "targets",
        "status",
        "warnings",
        "cache_invalidation",
        "recovered_from_incomplete_stage",
    }
)
ALLOWED_TARGET_FIELDS = frozenset(
    {
        "subject_type",
        "subject_id",
        "run_id",
        "root_relative_path",
        "canonical_path",
        "tree_fingerprint",
        "filesystem_dev",
        "filesystem_ino",
        "staging_path",
        "staged_dev",
        "staged_ino",
        "state",
        "fingerprint_invalidated",
        "error",
    }
)
KNOWN_TARGET_STATES = frozenset(
    {
        "planned",
        "staging_started",
        "staged",
        "staged_journal_incomplete",
        "staged_identity_unverified",
        "physical_delete_verified",
        "physical_deleted",
        "physical_delete_failed",
        "physical_delete_refused",
        "physical_delete_partial",
        "interrupted_staging",
        "recovered_from_incomplete_stage",
        "external_disappeared",
        "staging_failed",
        "locked_skip",
    }
)


class JournalDurabilityError(RuntimeError):
    """Genuine journal durability failure (not unsupported fsync)."""


class JournalClaimError(RuntimeError):
    """Could not claim retry ownership under the journal lock."""


class DirFsyncOutcome(str, Enum):
    OK = "ok"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class JournalLoadKind(str, Enum):
    MISSING = "MISSING"
    INCOMPATIBLE = "INCOMPATIBLE"
    CORRUPT_OR_UNSAFE = "CORRUPT_OR_UNSAFE"
    TERMINAL = "TERMINAL"
    RETRYABLE = "RETRYABLE"


TERMINAL_JOURNAL_STATUSES = frozenset(
    {
        "completed",
        "SUCCESS",
        "success",
        "NOOP",
        "ALREADY_EXECUTED",
        "BLOCKED",
        "STALE_PLAN",
    }
)
RETRYABLE_JOURNAL_STATUSES = frozenset(
    {
        "journaled",
        "interrupted",
        "retry_in_progress",
        "PARTIAL",
        "partial",
        "FAILED_BEFORE_MUTATION",
    }
)

# Target states that may still imply a staged remnant or incomplete mutation.
PENDING_TARGET_STATES = frozenset(
    {
        "planned",
        "staging_started",
        "staged",
        "interrupted_staging",
        "physical_delete_failed",
        "physical_delete_refused",
        "staged_journal_incomplete",
        "staged_identity_unverified",
        "physical_delete_partial",
        "physical_delete_verified",
        "recovered_from_incomplete_stage",
    }
)

# Target states that are intentionally complete with no staged remnant.
TERMINAL_SUCCESS_TARGET_STATES = frozenset(
    {
        "physical_deleted",
        "external_disappeared",
    }
)
TERMINAL_SKIP_TARGET_STATES = frozenset(
    {
        "locked_skip",
        "staging_failed",
    }
)


@dataclass(frozen=True)
class DirFsyncResult:
    outcome: DirFsyncOutcome
    message: str = ""


@dataclass(frozen=True)
class JournalLoadResult:
    kind: JournalLoadKind
    data: dict[str, Any] | None = None
    message: str = ""


def operations_dir(state_dir: Path) -> Path:
    return Path(state_dir) / "cleanup" / "operations"


def journal_claim_lock_path(state_dir: Path, operation_id: str) -> Path:
    """Lock file for journal claim (outside deletable run trees)."""
    operation_id = validate_operation_id(operation_id)
    return Path(state_dir) / "cleanup" / "journal_locks" / f"{operation_id}.claim.lock"


def _ensure_operations_dir(state_dir: Path) -> Path:
    state_root = Path(state_dir)
    state_root.mkdir(parents=True, exist_ok=True)
    cleanup = state_root / "cleanup"
    cleanup.mkdir(parents=True, exist_ok=True)
    try:
        st = cleanup.lstat()
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
            raise JournalDurabilityError(f"cleanup dir unsafe: {cleanup}")
    except OSError as exc:
        raise JournalDurabilityError(f"cleanup dir lstat failed: {exc}") from exc
    ops = cleanup / "operations"
    ops.mkdir(parents=True, exist_ok=True)
    try:
        st = ops.lstat()
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
            raise JournalDurabilityError(f"operations dir unsafe: {ops}")
    except OSError as exc:
        raise JournalDurabilityError(f"operations dir lstat failed: {exc}") from exc
    try:
        os.chmod(ops, 0o700)
    except OSError:
        pass
    return ops


def _dir_fsync_unsupported_errno(exc: OSError) -> bool:
    """True when directory fsync is unavailable on this fd/filesystem.

    Docker Desktop bind mounts (and some network FS) often return EBADF/EINVAL
    for directory fsync even after a successful O_RDONLY|O_DIRECTORY open. The
    journal file itself is already fsync'd; treat these as unsupported rather
    than aborting cleanup.
    """
    unsupported = {errno.EINVAL, errno.ENOTSUP, errno.EBADF}
    eopnotsupp = getattr(errno, "EOPNOTSUPP", -1)
    if eopnotsupp != -1:
        unsupported.add(eopnotsupp)
    return exc.errno in unsupported


def fsync_dir(directory: Path) -> DirFsyncResult:
    """Fsync directory; distinguish unsupported vs genuine failure."""
    try:
        flags = getattr(os, "O_RDONLY", 0)
        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY
        fd = os.open(str(directory), flags)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return DirFsyncResult(DirFsyncOutcome.OK)
    except (AttributeError, NotImplementedError) as exc:
        return DirFsyncResult(DirFsyncOutcome.UNSUPPORTED, str(exc))
    except OSError as exc:
        if _dir_fsync_unsupported_errno(exc):
            return DirFsyncResult(DirFsyncOutcome.UNSUPPORTED, str(exc))
        return DirFsyncResult(DirFsyncOutcome.FAILED, str(exc))


def _atomic_write_json(
    path: Path, payload: Mapping[str, Any], *, exclusive: bool = False
) -> DirFsyncResult:
    path = Path(path)
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            fd = os.open(str(path), flags, 0o600)
        except FileExistsError:
            raise
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                raise FileExistsError(str(path)) from exc
            raise JournalDurabilityError(f"exclusive create failed: {exc}") from exc
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(dict(payload), handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            try:
                path.unlink()
            except OSError:
                pass
            raise
        return fsync_dir(parent)

    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(parent))
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(dict(payload), handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temp), str(path))
        return fsync_dir(parent)
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


def new_operation_id() -> str:
    return f"{int(time.time())}_{secrets.token_hex(6)}"


def _target_record(
    target: CleanupTarget, staging_path: str | None = None
) -> dict[str, Any]:
    return {
        "subject_type": target.subject_type.value,
        "subject_id": target.subject_id,
        "run_id": target.run_id,
        "root_relative_path": target.root_relative_path,
        "canonical_path": target.canonical_path,
        "tree_fingerprint": target.tree_fingerprint,
        "filesystem_dev": target.filesystem_dev,
        "filesystem_ino": target.filesystem_ino,
        "staging_path": staging_path,
        "staged_dev": None,
        "staged_ino": None,
        "state": "planned",
    }


def write_operation(
    state_dir: Path,
    *,
    operation_id: str,
    plan: CleanupPlan,
    staging_destinations: Mapping[str, str] | None = None,
) -> Path:
    """Exclusively create a new operation journal before first staging rename."""
    operation_id = validate_operation_id(operation_id)
    staging_destinations = dict(staging_destinations or {})
    targets = [
        _target_record(t, staging_destinations.get(t.canonical_path))
        for t in plan.candidates
    ]
    payload = {
        "journal_schema_version": JOURNAL_SCHEMA_VERSION,
        "cleanup_policy_version": CLEANUP_POLICY_VERSION,
        "operation_id": operation_id,
        "plan_id": plan.plan_id,
        "mode": plan.mode.value,
        "policy_version": plan.policy_version,
        "created_at": time.time(),
        "roots": [
            {
                "kind": r.kind.value,
                "configured_path": r.configured_path,
                "canonical_path": r.canonical_path,
                "dev": r.dev,
                "ino": r.ino,
                "is_symlink": r.is_symlink,
                "exists": getattr(r, "exists", True),
            }
            for r in plan.roots
        ],
        "targets": targets,
        "status": "journaled",
    }
    ops = _ensure_operations_dir(state_dir)
    path = ops / f"{operation_id}.json"
    result = _atomic_write_json(path, payload, exclusive=True)
    if result.outcome is DirFsyncOutcome.FAILED:
        try:
            path.unlink()
        except OSError:
            pass
        raise JournalDurabilityError(
            f"directory fsync failed after journal create: {result.message}"
        )
    return path


def _validate_journal_payload(
    data: dict[str, Any],
    *,
    expected_operation_id: str,
    expected_policy_version: int | None,
    expected_schema_version: int | None,
) -> dict[str, Any]:
    unknown = set(data) - ALLOWED_TOP_LEVEL
    if unknown:
        raise ValueError(f"unknown journal fields: {sorted(unknown)}")
    if data.get("operation_id") != expected_operation_id:
        raise ValueError("journal operation_id mismatch")
    schema = data.get("journal_schema_version")
    policy = data.get("cleanup_policy_version", data.get("policy_version"))
    if expected_schema_version is not None and schema != expected_schema_version:
        raise ValueError("incompatible journal schema version")
    if expected_policy_version is not None and policy != expected_policy_version:
        raise ValueError("incompatible cleanup policy version")
    targets = data.get("targets")
    if not isinstance(targets, list):
        raise ValueError("targets must be a list")
    if len(targets) > MAX_TARGETS:
        raise ValueError("too many targets")
    seen: set[tuple] = set()
    for t in targets:
        if not isinstance(t, dict):
            raise ValueError("target must be object")
        unknown_t = set(t) - ALLOWED_TARGET_FIELDS
        if unknown_t:
            raise ValueError(f"unknown target fields: {sorted(unknown_t)}")
        for key in ("canonical_path", "root_relative_path", "subject_id", "run_id"):
            val = t.get(key)
            if isinstance(val, str) and len(val) > MAX_PATH_LEN:
                raise ValueError(f"{key} too long")
        fp = t.get("tree_fingerprint")
        if fp is not None and (
            not isinstance(fp, str) or not FINGERPRINT_RE.fullmatch(fp)
        ):
            raise ValueError("malformed tree_fingerprint")
        state = t.get("state")
        if state is not None and state not in KNOWN_TARGET_STATES:
            raise ValueError(f"unknown target state: {state}")
        ident = (
            t.get("subject_type"),
            t.get("subject_id"),
            t.get("run_id"),
            t.get("canonical_path"),
            t.get("filesystem_dev"),
            t.get("filesystem_ino"),
        )
        if ident in seen:
            raise ValueError("duplicate target identity")
        seen.add(ident)
    return data


def load_operation_typed(
    state_dir: Path,
    operation_id: str,
    *,
    expected_policy_version: int | None = None,
    expected_schema_version: int | None = None,
) -> JournalLoadResult:
    """Load a journal with a typed outcome (never collapses all failures to None)."""
    try:
        operation_id = validate_operation_id(operation_id)
    except ValueError as exc:
        return JournalLoadResult(JournalLoadKind.CORRUPT_OR_UNSAFE, message=str(exc))
    try:
        ops = _ensure_operations_dir(state_dir)
    except JournalDurabilityError as exc:
        return JournalLoadResult(JournalLoadKind.CORRUPT_OR_UNSAFE, message=str(exc))
    path = ops / f"{operation_id}.json"
    try:
        st = fd_ops.lstat_nofollow(path)
    except FileNotFoundError:
        return JournalLoadResult(JournalLoadKind.MISSING, message="journal missing")
    except OSError as exc:
        if getattr(exc, "errno", None) in {errno.ENOENT, errno.ENOTDIR}:
            return JournalLoadResult(JournalLoadKind.MISSING, message="journal missing")
        return JournalLoadResult(
            JournalLoadKind.CORRUPT_OR_UNSAFE, message=f"lstat failed: {exc}"
        )
    if stat.S_ISLNK(st.st_mode):
        return JournalLoadResult(
            JournalLoadKind.CORRUPT_OR_UNSAFE, message="journal is a symlink"
        )
    if not stat.S_ISREG(st.st_mode):
        return JournalLoadResult(
            JournalLoadKind.CORRUPT_OR_UNSAFE, message="journal is not a regular file"
        )
    if st.st_size > MAX_JOURNAL_BYTES:
        return JournalLoadResult(
            JournalLoadKind.CORRUPT_OR_UNSAFE, message="journal exceeds size limit"
        )
    try:
        fd = fd_ops.open_file_nofollow(path)
        try:
            raw = os.read(fd, MAX_JOURNAL_BYTES + 1)
        finally:
            fd_ops.close_quiet(fd)
    except (OSError, fd_ops.FdOpsUnsupportedError) as exc:
        return JournalLoadResult(
            JournalLoadKind.CORRUPT_OR_UNSAFE, message=f"open/read failed: {exc}"
        )
    if len(raw) > MAX_JOURNAL_BYTES:
        return JournalLoadResult(
            JournalLoadKind.CORRUPT_OR_UNSAFE, message="journal exceeds size limit"
        )
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return JournalLoadResult(
            JournalLoadKind.CORRUPT_OR_UNSAFE, message=f"json decode failed: {exc}"
        )
    if not isinstance(data, dict):
        return JournalLoadResult(
            JournalLoadKind.CORRUPT_OR_UNSAFE, message="journal root is not an object"
        )
    schema = data.get("journal_schema_version")
    policy = data.get("cleanup_policy_version", data.get("policy_version"))
    if expected_schema_version is not None and schema != expected_schema_version:
        return JournalLoadResult(
            JournalLoadKind.INCOMPATIBLE,
            message="incompatible journal schema version",
        )
    if expected_policy_version is not None and policy != expected_policy_version:
        return JournalLoadResult(
            JournalLoadKind.INCOMPATIBLE,
            message="incompatible cleanup policy version",
        )
    try:
        validated = _validate_journal_payload(
            data,
            expected_operation_id=operation_id,
            expected_policy_version=None,  # already checked
            expected_schema_version=None,
        )
    except ValueError as exc:
        return JournalLoadResult(JournalLoadKind.CORRUPT_OR_UNSAFE, message=str(exc))
    status = str(validated.get("status") or "")
    if status in TERMINAL_JOURNAL_STATUSES:
        return JournalLoadResult(JournalLoadKind.TERMINAL, data=validated)
    if status in RETRYABLE_JOURNAL_STATUSES or status == "":
        return JournalLoadResult(JournalLoadKind.RETRYABLE, data=validated)
    # Unknown status: not silently reclaimable
    return JournalLoadResult(
        JournalLoadKind.CORRUPT_OR_UNSAFE,
        data=validated,
        message=f"unknown journal status: {status!r}",
    )


def load_operation(
    state_dir: Path,
    operation_id: str,
    *,
    expected_policy_version: int | None = None,
    expected_schema_version: int | None = None,
) -> dict[str, Any] | None:
    """Compatibility wrapper: returns data only for RETRYABLE/TERMINAL loads."""
    result = load_operation_typed(
        state_dir,
        operation_id,
        expected_policy_version=expected_policy_version,
        expected_schema_version=expected_schema_version,
    )
    if result.kind in {JournalLoadKind.RETRYABLE, JournalLoadKind.TERMINAL}:
        return result.data
    return None


def update_target_state(
    state_dir: Path,
    operation_id: str,
    *,
    canonical_path: str,
    state: str,
    staging_path: str | None = None,
    staged_dev: int | None = None,
    staged_ino: int | None = None,
    extra: Mapping[str, Any] | None = None,
) -> DirFsyncResult:
    operation_id = validate_operation_id(operation_id)
    path = operations_dir(state_dir) / f"{operation_id}.json"
    data = load_operation(
        state_dir,
        operation_id,
        expected_policy_version=CLEANUP_POLICY_VERSION,
        expected_schema_version=JOURNAL_SCHEMA_VERSION,
    )
    if data is None:
        raise FileNotFoundError(f"cleanup journal missing: {operation_id}")
    updated = False
    for target in data.get("targets", []):
        if target.get("canonical_path") == canonical_path:
            target["state"] = state
            if staging_path is not None:
                target["staging_path"] = staging_path
            if staged_dev is not None:
                target["staged_dev"] = staged_dev
            if staged_ino is not None:
                target["staged_ino"] = staged_ino
            if extra:
                target.update(dict(extra))
            updated = True
            break
    if not updated:
        raise KeyError(f"target not in journal: {canonical_path}")
    data["updated_at"] = time.time()
    return _atomic_write_json(path, data, exclusive=False)


def update_operation_status(
    state_dir: Path, operation_id: str, status: str, **extra: Any
) -> DirFsyncResult:
    operation_id = validate_operation_id(operation_id)
    path = operations_dir(state_dir) / f"{operation_id}.json"
    data = load_operation(
        state_dir,
        operation_id,
        expected_policy_version=CLEANUP_POLICY_VERSION,
        expected_schema_version=JOURNAL_SCHEMA_VERSION,
    )
    if data is None:
        raise FileNotFoundError(f"cleanup journal missing: {operation_id}")
    data["status"] = status
    data["updated_at"] = time.time()
    data.update(extra)
    return _atomic_write_json(path, data, exclusive=False)


def claim_retry_ownership(state_dir: Path, operation_id: str) -> DirFsyncResult:
    """Claim retry under a dedicated FileLock; reject unknown statuses."""
    operation_id = validate_operation_id(operation_id)
    lock_path = journal_claim_lock_path(state_dir, operation_id)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        st = lock_path.parent.lstat()
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
            raise JournalClaimError(f"journal lock dir unsafe: {lock_path.parent}")
    except OSError as exc:
        raise JournalClaimError(f"journal lock dir lstat failed: {exc}") from exc

    file_lock = FileLock(lock_path.with_suffix(""), timeout=5, blocking=False)
    file_lock.lock_file = lock_path
    if not file_lock.acquire():
        raise JournalClaimError("could not acquire journal claim lock")
    try:
        loaded = load_operation_typed(
            state_dir,
            operation_id,
            expected_policy_version=CLEANUP_POLICY_VERSION,
            expected_schema_version=JOURNAL_SCHEMA_VERSION,
        )
        if loaded.kind is JournalLoadKind.MISSING:
            raise JournalClaimError("cleanup journal missing")
        if loaded.kind is JournalLoadKind.INCOMPATIBLE:
            raise JournalClaimError(loaded.message or "incompatible journal")
        if loaded.kind is JournalLoadKind.CORRUPT_OR_UNSAFE:
            raise JournalClaimError(loaded.message or "unsafe journal")
        if loaded.kind is JournalLoadKind.TERMINAL:
            raise JournalClaimError("operation already completed")
        data = loaded.data
        if data is None:
            raise JournalClaimError("retryable journal missing payload")
        status = data.get("status")
        if status not in RETRYABLE_JOURNAL_STATUSES and status is not None:
            raise JournalClaimError(f"status not reclaimable: {status!r}")
        return update_operation_status(state_dir, operation_id, "retry_in_progress")
    finally:
        file_lock.release()


def list_pending_staging(state_dir: Path) -> list[dict[str, Any]]:
    pending: list[dict[str, Any]] = []
    root = operations_dir(state_dir)
    if not root.is_dir():
        return pending
    for path in sorted(root.glob("*.json")):
        try:
            stem = path.stem
            validate_operation_id(stem)
            data = load_operation(
                state_dir,
                stem,
                expected_policy_version=CLEANUP_POLICY_VERSION,
                expected_schema_version=JOURNAL_SCHEMA_VERSION,
            )
        except ValueError:
            continue
        if data is None:
            continue
        op_status = str(data.get("status") or "")
        if op_status in TERMINAL_JOURNAL_STATUSES:
            continue
        op_id = data.get("operation_id") or path.stem
        for target in data.get("targets", []):
            state = target.get("state")
            if state in PENDING_TARGET_STATES:
                pending.append(
                    {
                        "operation_id": op_id,
                        "plan_id": data.get("plan_id"),
                        "mode": data.get("mode"),
                        "operation_status": op_status,
                        **target,
                    }
                )
    return pending


def derive_staging_path_from_journal_target(
    output_root: Path, operation_id: str, target: Mapping[str, Any]
) -> Path:
    from transcriptx.web.services.run_cleanup.models import (
        CleanupTarget,
        EntryClassification,
    )

    operation_id = validate_operation_id(operation_id)
    fake = CleanupTarget(
        subject_type=SubjectType(str(target["subject_type"])),
        subject_id=str(target["subject_id"]),
        run_id=str(target["run_id"]),
        root_relative_path=str(target.get("root_relative_path") or ""),
        canonical_path=str(target["canonical_path"]),
        mtime_ns=0,
        filesystem_dev=int(target.get("filesystem_dev") or 0),
        filesystem_ino=int(target.get("filesystem_ino") or 0),
        size_estimate_bytes=0,
        file_count=0,
        tree_fingerprint=str(target.get("tree_fingerprint") or ("0" * 64)),
        safety_status=EntryClassification.eligible,
    )
    # Prefer stored basename when it matches collision-proof derivation
    safe_name = collision_proof_staging_basename(fake)
    return Path(output_root) / STAGING_DIR_NAME / operation_id / safe_name


def is_journal_recognised_staging_path(
    state_dir: Path,
    staging_path: Path | str,
    *,
    operation_id: str,
    subject_type: str,
    subject_id: str,
    run_id: str,
    canonical_path: str,
    outputs_dir: Path,
    group_outputs_dir: Path,
    expected_policy_version: int | None = CLEANUP_POLICY_VERSION,
    expected_schema_version: int | None = JOURNAL_SCHEMA_VERSION,
) -> bool:
    """True only if the exact operation journal derives this staging path."""
    try:
        operation_id = validate_operation_id(operation_id)
    except ValueError:
        return False
    data = load_operation(
        state_dir,
        operation_id,
        expected_policy_version=expected_policy_version,
        expected_schema_version=expected_schema_version,
    )
    if data is None:
        return False
    want = Path(staging_path)
    target = None
    for t in data.get("targets", []):
        if (
            t.get("subject_type") == subject_type
            and t.get("subject_id") == subject_id
            and t.get("run_id") == run_id
            and t.get("canonical_path") == canonical_path
        ):
            target = t
            break
    if target is None:
        return False
    root_base = (
        Path(group_outputs_dir)
        if subject_type == SubjectType.group.value
        else Path(outputs_dir)
    )
    derived = derive_staging_path_from_journal_target(root_base, operation_id, target)
    if want != derived and Path(want) != Path(derived):
        # Compare as posix path strings without resolve()
        if str(want) != str(derived):
            return False
    if want.parent != derived.parent:
        return False
    recorded = target.get("staging_path")
    if recorded is not None and str(recorded) != str(derived):
        return False
    return True


def mode_from_journal(data: Mapping[str, Any]) -> CleanupMode | None:
    raw = data.get("mode")
    if raw is None:
        return None
    try:
        return CleanupMode(raw)
    except ValueError:
        return None
