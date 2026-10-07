"""Keep-file salvage for DELETE_OLD cleanup (copy into ``.retained`` sidecar)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from transcriptx.web.services.run_cleanup.models import (
    RETAINED_DIR_NAME,
    CleanupRetainPolicy,
    CleanupTarget,
)

_HUMAN_TRANSCRIPT_SUFFIXES = frozenset({".txt", ".csv", ".srt", ".vtt"})
_REPORT_NAMES = frozenset({"report.md", "report.txt"})


def iter_keep_relative_paths(
    run_dir: Path, policy: CleanupRetainPolicy
) -> list[str]:
    """Return run-relative posix paths that match the retain policy."""
    if not policy.enabled or not run_dir.is_dir():
        return []
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(run_dir, followlinks=False):
        # Never walk into nested retention or staging trees.
        dirnames[:] = [
            d
            for d in dirnames
            if d not in {RETAINED_DIR_NAME, ".cleanup_staging"} and not d.startswith(".")
        ]
        base = Path(dirpath)
        for name in filenames:
            if name.startswith("."):
                continue
            abs_path = base / name
            try:
                rel = abs_path.relative_to(run_dir).as_posix()
            except ValueError:
                continue
            if policy.keep_human_readable and _is_human_readable(rel, name):
                found.append(rel)
                continue
            if policy.keep_llm_summaries and _is_llm_summary(name):
                found.append(rel)
    found.sort()
    return found


def _is_human_readable(rel: str, name: str) -> bool:
    if name in _REPORT_NAMES:
        return True
    parts = Path(rel).parts
    if len(parts) >= 2 and parts[0] == "transcripts":
        return Path(name).suffix.lower() in _HUMAN_TRANSCRIPT_SUFFIXES
    return False


def _is_llm_summary(name: str) -> bool:
    lower = name.lower()
    return lower.endswith("_llm_summary.md") or lower.endswith("_llm_summary.json")


def salvage_keep_files(
    target: CleanupTarget,
    policy: CleanupRetainPolicy,
) -> tuple[int, tuple[str, ...]]:
    """Copy keep-files to ``{subject}/.retained/{run_id}/…`` before staging.

    Returns ``(copied_count, errors)``. Idempotent: existing identical
    destinations are left in place; existing different content is overwritten.
    """
    if not policy.enabled:
        return 0, ()
    run_dir = Path(target.canonical_path)
    if not run_dir.is_dir():
        return 0, ()
    rels = iter_keep_relative_paths(run_dir, policy)
    if not rels:
        return 0, ()

    subject_dir = run_dir.parent
    dest_root = subject_dir / RETAINED_DIR_NAME / target.run_id
    errors: list[str] = []
    copied = 0
    try:
        dest_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return 0, (f"could not create retain sidecar {dest_root}: {exc}",)

    for rel in rels:
        src = run_dir / rel
        dest = dest_root / rel
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest, follow_symlinks=False)
            copied += 1
        except OSError as exc:
            errors.append(f"retain copy failed {rel}: {exc}")
    return copied, tuple(errors)
