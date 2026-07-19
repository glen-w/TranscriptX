"""Path-safe inventory of currently retained committed analysis runs.

A run is committed when ``run_results.json`` loads and validates. This is
intentionally independent of user-visible artifact filters (``RunIndex``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Literal, Optional

from transcriptx.core.pipeline.manifest_loader import load_run_results
from transcriptx.core.utils.logger import get_logger

logger = get_logger()

DEFAULT_MAX_COMMITTED_RUNS = 10_000

TargetType = Literal["transcript", "group"]


@dataclass(frozen=True)
class CommittedRunRef:
    """One retained committed run (internal identity; not for metric labels)."""

    run_root: Path
    target_type: TargetType
    run_id: str
    run_results: Dict[str, Any]


@dataclass(frozen=True)
class InventoryScanResult:
    runs: tuple[CommittedRunRef, ...]
    candidates_seen: int
    errors: int
    truncated: bool


def _safe_isdir(entry: os.DirEntry[str]) -> bool:
    try:
        return entry.is_dir(follow_symlinks=False)
    except OSError:
        return False


def _iter_subject_dirs(root: Path, *, skip_names: frozenset[str]) -> Iterator[Path]:
    if not root.is_dir():
        return
    try:
        with os.scandir(root) as entries:
            subjects = sorted(
                (e for e in entries if _safe_isdir(e) and not e.name.startswith(".")),
                key=lambda e: e.name,
            )
    except OSError as exc:
        logger.warning("cannot scandir outputs root %s: %s", root, exc)
        return
    for entry in subjects:
        if entry.name in skip_names:
            continue
        yield Path(entry.path)


def _iter_run_dirs(subject_dir: Path) -> Iterator[Path]:
    try:
        with os.scandir(subject_dir) as entries:
            runs = sorted(
                (e for e in entries if _safe_isdir(e) and not e.name.startswith(".")),
                key=lambda e: e.name,
            )
    except OSError as exc:
        logger.warning("cannot scandir subject dir %s: %s", subject_dir, exc)
        return
    for entry in runs:
        yield Path(entry.path)


def _try_load_committed(
    run_root: Path, *, target_type: TargetType
) -> tuple[Optional[CommittedRunRef], bool]:
    """Return ``(ref_or_none, is_error)``.

    Missing/invalid ``run_results`` is not an error (run simply not committed).
    Unexpected IO failures are errors and are isolated by the caller.
    """
    path = run_root / "run_results.json"
    try:
        if not path.is_file() or path.is_symlink():
            return None, False
        payload = load_run_results(path)
    except (OSError, UnicodeError) as exc:
        logger.warning("committed-run IO fault at %s: %s", run_root, exc)
        return None, True
    except Exception:
        # Validation / schema failures: not committed, not a scan fault.
        return None, False
    run_id = str(payload.get("run_id") or "").strip()
    if not run_id:
        return None, False
    return (
        CommittedRunRef(
            run_root=run_root,
            target_type=target_type,
            run_id=run_id,
            run_results=payload,
        ),
        False,
    )


def scan_committed_runs(
    *,
    outputs_dir: Path,
    group_outputs_dir: Optional[Path] = None,
    max_runs: int = DEFAULT_MAX_COMMITTED_RUNS,
) -> InventoryScanResult:
    """Scan retained transcript + group run trees for valid ``run_results.json``.

    Deterministic order (subject name, then run id). Stops after ``max_runs``
    successful commits. Per-candidate failures are isolated and counted.
    """
    if max_runs < 0:
        raise ValueError("max_runs must be >= 0")

    groups_root = (
        Path(group_outputs_dir)
        if group_outputs_dir is not None
        else Path(outputs_dir) / "groups"
    )
    outputs_root = Path(outputs_dir)

    found: List[CommittedRunRef] = []
    candidates = 0
    errors = 0
    truncated = False

    def _consume(run_root: Path, target_type: TargetType) -> bool:
        nonlocal candidates, errors, truncated
        candidates += 1
        try:
            ref, is_error = _try_load_committed(run_root, target_type=target_type)
        except Exception as exc:
            errors += 1
            logger.warning("committed-run scan fault at %s: %s", run_root, exc)
            return True
        if is_error:
            errors += 1
            return True
        if ref is None:
            return True
        if len(found) >= max_runs:
            # Another committed run exists beyond the cap.
            truncated = True
            return False
        found.append(ref)
        return True

    for subject in _iter_subject_dirs(outputs_root, skip_names=frozenset({"groups"})):
        for run_root in _iter_run_dirs(subject):
            if not _consume(run_root, "transcript"):
                return InventoryScanResult(
                    runs=tuple(found),
                    candidates_seen=candidates,
                    errors=errors,
                    truncated=truncated,
                )

    for group_dir in _iter_subject_dirs(groups_root, skip_names=frozenset()):
        for run_root in _iter_run_dirs(group_dir):
            if not _consume(run_root, "group"):
                return InventoryScanResult(
                    runs=tuple(found),
                    candidates_seen=candidates,
                    errors=errors,
                    truncated=truncated,
                )

    return InventoryScanResult(
        runs=tuple(found),
        candidates_seen=candidates,
        errors=errors,
        truncated=truncated,
    )
