"""Shared run-tree mutation gate and per-run writer locks.

Lock files live under STATE_DIR (outside deletable run trees).
Uses FileLock; see tests/core/utils/test_run_writer_locks.py for characterization.
"""

from __future__ import annotations

import hashlib
import os
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from transcriptx.core.utils.file_lock import FileLock, LockAcquisitionError
from transcriptx.core.utils.paths import STATE_DIR

__all__ = [
    "LockAcquisitionError",
    "RunWriterLock",
    "RunWriterLease",
    "run_tree_mutation_gate",
    "try_run_tree_mutation_gate",
    "per_run_lock",
    "try_per_run_lock",
    "run_lock_path_for_canonical_root",
    "mutation_gate_lock_path",
    "assert_lease_for_run",
]


class LockDirectoryUnsafeError(OSError):
    """Lock directory is a symlink, wrong type, or outside state_dir."""


def mutation_gate_lock_path(state_dir: Path | None = None) -> Path:
    """Path for the shared run-tree mutation gate lock file."""
    root = Path(state_dir) if state_dir is not None else Path(STATE_DIR)
    return root / "cleanup" / "run_tree_mutation.lock"


def run_lock_path_for_canonical_root(
    canonical_run_root: Path | str,
    *,
    state_dir: Path | None = None,
) -> Path:
    """Derive a per-run lock path outside deletable run trees."""
    from transcriptx.core.utils.path_canonical import canonicalise_path

    root = Path(state_dir) if state_dir is not None else Path(STATE_DIR)
    canon = canonicalise_path(canonical_run_root)
    encoded = canon.encode("utf-8")
    payload = b"v1\0" + str(len(encoded)).encode("ascii") + b"\0" + encoded
    digest = hashlib.sha256(payload).hexdigest()
    lock_dir = root / "run_locks"
    return lock_dir / f"{digest}.lock"


def _lstat_real_dir(path: Path, *, label: str) -> os.stat_result:
    try:
        st = path.lstat()
    except OSError as exc:
        raise LockDirectoryUnsafeError(f"cannot lstat {label} {path}: {exc}") from exc
    if stat.S_ISLNK(st.st_mode):
        raise LockDirectoryUnsafeError(f"{label} must not be a symlink: {path}")
    if not stat.S_ISDIR(st.st_mode):
        raise LockDirectoryUnsafeError(f"{label} must be a directory: {path}")
    return st


def _ensure_under_state(path: Path, state_root: Path) -> None:
    from transcriptx.core.utils.path_canonical import canonicalise_path

    try:
        Path(canonicalise_path(path)).relative_to(Path(canonicalise_path(state_root)))
    except ValueError as exc:
        raise LockDirectoryUnsafeError(
            f"lock path {path} is not under state_dir {state_root}"
        ) from exc


def _ensure_lock_dir(path: Path, *, state_dir: Path | None = None) -> None:
    """Create lock parent as a real directory (not symlink); fail closed."""
    state_root = Path(state_dir) if state_dir is not None else Path(STATE_DIR)
    parent = path.parent
    # Ensure ancestor chain under state_dir
    if parent.name in {"cleanup", "run_locks"}:
        # Verify state_root itself if it exists
        if state_root.exists() or os.path.lexists(str(state_root)):
            _lstat_real_dir(state_root, label="state_dir")
        # Create state_root if missing
        state_root.mkdir(parents=True, exist_ok=True)
        _lstat_real_dir(state_root, label="state_dir")

        if parent.name == "cleanup":
            parent.mkdir(parents=True, exist_ok=True)
            _lstat_real_dir(parent, label="cleanup lock dir")
            _ensure_under_state(parent, state_root)
        else:
            # run_locks
            parent.mkdir(parents=True, exist_ok=True)
            _lstat_real_dir(parent, label="run_locks dir")
            _ensure_under_state(parent, state_root)
    else:
        parent.mkdir(parents=True, exist_ok=True)
        _lstat_real_dir(parent, label="lock directory")
        _ensure_under_state(parent, state_root)

    try:
        os.chmod(parent, 0o700)
    except OSError:
        # Permissions are not part of the safety identity contract
        pass


@dataclass(frozen=True)
class RunWriterLease:
    """Proof that the caller holds the per-run lock for a canonical run root."""

    canonical_run_root: str
    lock_file: str


def assert_lease_for_run(
    lease: RunWriterLease | None, canonical_run_root: Path | str
) -> None:
    """Reject absent/wrong lease for internal writers."""
    from transcriptx.core.utils.path_canonical import canonicalise_path

    if lease is None:
        raise LockAcquisitionError("RunWriterLease required for this write")
    expected = canonicalise_path(canonical_run_root)
    if lease.canonical_run_root != expected:
        raise LockAcquisitionError(
            f"RunWriterLease root mismatch: {lease.canonical_run_root!r} != {expected!r}"
        )


class RunWriterLock:
    """Thin wrapper around FileLock with explicit non-blocking try_acquire."""

    def __init__(
        self,
        lock_target: Path,
        *,
        timeout: float = 30,
        blocking: bool = True,
        canonical_run_root: str | None = None,
    ) -> None:
        self._lock_file = Path(lock_target)
        self._canonical_run_root = canonical_run_root
        if self._lock_file.suffix == ".lock":
            sentinel = self._lock_file.with_suffix("")
        else:
            sentinel = self._lock_file
            self._lock_file = Path(str(self._lock_file) + ".lock")
        timeout_int = max(1, int(timeout)) if timeout >= 1 else 1
        self._file_lock = FileLock(sentinel, timeout=timeout_int, blocking=blocking)
        self._file_lock.lock_file = self._lock_file
        self.timeout = timeout
        self.blocking = blocking

    @property
    def acquired(self) -> bool:
        return self._file_lock.acquired

    @property
    def lock_file(self) -> Path:
        return self._lock_file

    def lease(self) -> RunWriterLease | None:
        if self._canonical_run_root is None or not self.acquired:
            return None
        return RunWriterLease(
            canonical_run_root=self._canonical_run_root,
            lock_file=str(self._lock_file),
        )

    def acquire(self) -> bool:
        self._file_lock.lock_file = self._lock_file
        return self._file_lock.acquire()

    def try_acquire(self) -> bool:
        prev = self._file_lock.blocking
        self._file_lock.blocking = False
        try:
            self._file_lock.lock_file = self._lock_file
            return self._file_lock.acquire()
        finally:
            self._file_lock.blocking = prev

    def release(self) -> None:
        self._file_lock.release()

    def __enter__(self) -> "RunWriterLock":
        ok = self.acquire()
        if not ok and self.blocking:
            raise LockAcquisitionError(
                f"Could not acquire run writer lock within {self.timeout}s: {self._lock_file}"
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()


@contextmanager
def run_tree_mutation_gate(
    *,
    state_dir: Path | None = None,
    timeout: float = 120,
    blocking: bool = True,
) -> Iterator[RunWriterLock]:
    """Acquire the shared run-tree mutation gate."""
    path = mutation_gate_lock_path(state_dir)
    _ensure_lock_dir(path, state_dir=state_dir)
    lock = RunWriterLock(path, timeout=timeout, blocking=blocking)
    with lock:
        yield lock


def try_run_tree_mutation_gate(
    *,
    state_dir: Path | None = None,
) -> RunWriterLock | None:
    """Non-blocking acquire of mutation gate. Returns lock or None."""
    path = mutation_gate_lock_path(state_dir)
    _ensure_lock_dir(path, state_dir=state_dir)
    lock = RunWriterLock(path, blocking=False)
    if lock.try_acquire():
        return lock
    return None


@contextmanager
def per_run_lock(
    canonical_run_root: Path | str,
    *,
    state_dir: Path | None = None,
    timeout: float = 30,
    blocking: bool = True,
) -> Iterator[RunWriterLock]:
    """Acquire the per-run writer lock for a canonical run root."""
    from transcriptx.core.utils.path_canonical import canonicalise_path

    path = run_lock_path_for_canonical_root(canonical_run_root, state_dir=state_dir)
    _ensure_lock_dir(path, state_dir=state_dir)
    lock = RunWriterLock(
        path,
        timeout=timeout,
        blocking=blocking,
        canonical_run_root=canonicalise_path(canonical_run_root),
    )
    with lock:
        yield lock


def try_per_run_lock(
    canonical_run_root: Path | str,
    *,
    state_dir: Path | None = None,
) -> RunWriterLock | None:
    """Non-blocking per-run lock. Returns lock or None."""
    from transcriptx.core.utils.path_canonical import canonicalise_path

    path = run_lock_path_for_canonical_root(canonical_run_root, state_dir=state_dir)
    _ensure_lock_dir(path, state_dir=state_dir)
    lock = RunWriterLock(
        path,
        blocking=False,
        canonical_run_root=canonicalise_path(canonical_run_root),
    )
    if lock.try_acquire():
        return lock
    return None
