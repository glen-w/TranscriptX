"""Cross-session analysis-in-progress locks (per transcript or group).

Distinct from per-run writer locks: those serialize writes inside one run
directory. These claim “this transcript/group is already being analysed”.

Lock files live under ``STATE_DIR/analysis_locks/``. FileLock uses flock, so a
dead process drops the claim. Probe from a thread that does **not** already
hold the lock (Diagnostics); same-thread probe is re-entrant and would lie.
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Literal

from transcriptx.core.utils.paths import STATE_DIR
from transcriptx.core.utils.run_writer_locks import RunWriterLock, _ensure_lock_dir

__all__ = [
    "AnalysisBusyError",
    "analysis_lock_held",
    "analysis_lock_path",
    "canonical_transcript_lock_identity",
    "group_analysis_lock",
    "try_group_analysis_lock",
    "try_transcript_analysis_lock",
    "transcript_analysis_lock",
]

LockKind = Literal["transcript", "group"]


class AnalysisBusyError(RuntimeError):
    """Another analysis already holds the transcript or group claim."""

    def __init__(
        self,
        message: str,
        *,
        kind: LockKind,
        identity: str,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.identity = identity


def canonical_transcript_lock_identity(transcript_path: Path | str) -> str:
    from transcriptx.core.utils.path_canonical import canonicalise_path

    return canonicalise_path(transcript_path)


def canonical_group_lock_identity(group_uuid: str) -> str:
    return str(group_uuid).strip()


def analysis_lock_path(
    *,
    kind: LockKind,
    identity: str,
    state_dir: Path | None = None,
) -> Path:
    root = Path(state_dir) if state_dir is not None else Path(STATE_DIR)
    encoded = identity.encode("utf-8")
    payload = b"v1\0" + kind.encode("ascii") + b"\0" + encoded
    digest = hashlib.sha256(payload).hexdigest()
    return root / "analysis_locks" / f"{digest}.lock"


def _acquire(
    *,
    kind: LockKind,
    identity: str,
    state_dir: Path | None,
    blocking: bool,
) -> RunWriterLock | None:
    path = analysis_lock_path(kind=kind, identity=identity, state_dir=state_dir)
    _ensure_lock_dir(path, state_dir=state_dir)
    lock = RunWriterLock(path, blocking=blocking, timeout=1)
    if blocking:
        if not lock.acquire():
            return None
        return lock
    if lock.try_acquire():
        return lock
    return None


def try_transcript_analysis_lock(
    transcript_path: Path | str,
    *,
    state_dir: Path | None = None,
) -> RunWriterLock | None:
    identity = canonical_transcript_lock_identity(transcript_path)
    return _acquire(
        kind="transcript", identity=identity, state_dir=state_dir, blocking=False
    )


def try_group_analysis_lock(
    group_uuid: str,
    *,
    state_dir: Path | None = None,
) -> RunWriterLock | None:
    identity = canonical_group_lock_identity(group_uuid)
    if not identity:
        raise ValueError("group_uuid is required for group analysis lock")
    return _acquire(
        kind="group", identity=identity, state_dir=state_dir, blocking=False
    )


def analysis_lock_held(
    *,
    kind: LockKind,
    identity: str,
    state_dir: Path | None = None,
) -> bool:
    """Return True when another holder has the claim.

    Implementation: non-blocking try-acquire. Success means nobody holds it
    (release immediately). Failure means the claim is live.
    """
    if kind == "transcript":
        identity = canonical_transcript_lock_identity(identity)
    else:
        identity = canonical_group_lock_identity(identity)
        if not identity:
            return False
    lock = _acquire(
        kind=kind, identity=identity, state_dir=state_dir, blocking=False
    )
    if lock is None:
        return True
    lock.release()
    return False


@contextmanager
def transcript_analysis_lock(
    transcript_path: Path | str,
    *,
    state_dir: Path | None = None,
) -> Iterator[RunWriterLock]:
    identity = canonical_transcript_lock_identity(transcript_path)
    lock = try_transcript_analysis_lock(transcript_path, state_dir=state_dir)
    if lock is None:
        raise AnalysisBusyError(
            "Analysis already running for this transcript",
            kind="transcript",
            identity=identity,
        )
    try:
        yield lock
    finally:
        lock.release()


@contextmanager
def group_analysis_lock(
    group_uuid: str,
    *,
    state_dir: Path | None = None,
) -> Iterator[RunWriterLock]:
    identity = canonical_group_lock_identity(group_uuid)
    lock = try_group_analysis_lock(group_uuid, state_dir=state_dir)
    if lock is None:
        raise AnalysisBusyError(
            "Analysis already running for this group",
            kind="group",
            identity=identity,
        )
    try:
        yield lock
    finally:
        lock.release()
