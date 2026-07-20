"""Run-finalization lock shared by chart descriptions, synthesis, and manifest.

Acquisition order:
1. This run-finalization lock — acquired regardless of whether group synthesis
   is selected. Covers chart-description publication, group synthesis, and the
   single final manifest write.
2. No nested chart-description or synthesis locks while this lock is held.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from transcriptx.core.analysis.chart_descriptions.schemas import LOCK_TIMEOUT_SECONDS
from transcriptx.core.utils.file_lock import FileLock, LockAcquisitionError

RUN_FINALIZATION_LOCK_NAME = ".run_finalization.lock"


class RunFinalizationLockTimeout(RuntimeError):
    """Raised when the run-finalization lock cannot be acquired in time."""

    error_code = "RUN_FINALIZATION_LOCK_TIMEOUT"


def run_finalization_lock_path(run_root: Path) -> Path:
    return Path(run_root) / RUN_FINALIZATION_LOCK_NAME


@contextmanager
def run_finalization_lock(
    run_root: Path,
    *,
    timeout: float = LOCK_TIMEOUT_SECONDS,
) -> Iterator[None]:
    """Exclusive lock for chart descriptions → synthesis → manifest."""
    root = Path(run_root)
    root.mkdir(parents=True, exist_ok=True)
    target = run_finalization_lock_path(root)
    target.touch(exist_ok=True)
    try:
        with FileLock(target, timeout=timeout, blocking=True):
            yield
    except LockAcquisitionError as exc:
        raise RunFinalizationLockTimeout(
            f"Could not acquire run-finalization lock within {timeout}s"
        ) from exc
