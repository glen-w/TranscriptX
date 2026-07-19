"""Per-group synthesis lock.

Lock acquisition order (documented):
1. Group-run synthesis lock (this module) — must be acquired before writing or
   reading authoritative collect files, generation publish, synthesis manifest
   updates, or GC under ``.group_llm_synthesis/``.
2. No other locks are required in v1. Do not acquire unrelated locks while
   holding this lock unless their documented order is strictly after this one.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from transcriptx.core.analysis.group_llm_synthesis import errors as err
from transcriptx.core.analysis.group_llm_synthesis.paths import (
    lock_path,
    synthesis_root,
)
from transcriptx.core.analysis.group_llm_synthesis.schemas import LOCK_TIMEOUT_SECONDS
from transcriptx.core.utils.file_lock import FileLock, LockAcquisitionError


class SynthesisLockTimeout(RuntimeError):
    """Raised when the synthesis lock cannot be acquired in time."""

    error_code = err.SYNTHESIS_LOCK_TIMEOUT


@contextmanager
def synthesis_lock(
    run_root: Path,
    *,
    timeout: float = LOCK_TIMEOUT_SECONDS,
) -> Iterator[None]:
    """Exclusive lock covering collect write/read, commit, ACTIVE, and manifest."""
    root = synthesis_root(run_root)
    root.mkdir(parents=True, exist_ok=True)
    target = lock_path(run_root)
    target.touch(exist_ok=True)
    try:
        with FileLock(target, timeout=timeout, blocking=True):
            yield
    except LockAcquisitionError as exc:
        raise SynthesisLockTimeout(
            f"Could not acquire group LLM synthesis lock within {timeout}s"
        ) from exc
