"""Admit raw engine transcripts from ``originals/`` into the managed library.

Host helpers such as ``whispermlx-missing`` and ``inbox-watch`` write JSON
(or copied SRT/VTT) under ``transcripts/originals/``. This module runs the
same ``admit_and_register`` path as Import Transcript / Settings → Watcher.

When the source already lives in ``originals/``, the archive step reuses that
path (no ``foo (1).json`` duplicate). Streamlit never executes this module;
``inbox-watch --admit`` subprocesses ``python -m transcriptx.admit_originals``.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from transcriptx.io.admit_and_register import (
    AdmitOutcome,
    AdmitOutcomeKind,
    admit_and_register,
)
from transcriptx.io.import_admission import extension_is_supported
from transcriptx.io.managed_import_workflow import StagingCleanupPolicy

# ``foo (1).json``-style originals archives from a prior managed import.
_DISAMBIG_STEM_RE = re.compile(r"^.+ \(\d+\)$")

_SUCCESS_KINDS = frozenset(
    {
        AdmitOutcomeKind.IMPORTED_AND_REGISTERED,
        AdmitOutcomeKind.PARTIAL_STATE_REPAIRED,
        AdmitOutcomeKind.REGISTRATION_RECOVERED,
        AdmitOutcomeKind.REGISTRATION_FAILED_AFTER_ARTIFACT_COMMIT,
    }
)
_SKIP_KINDS = frozenset(
    {
        AdmitOutcomeKind.ALREADY_MANAGED,
        AdmitOutcomeKind.CONCURRENT_SKIP,
    }
)


@dataclass
class AdmitOriginalsStats:
    admitted: int = 0
    skipped: int = 0
    failed: int = 0
    admitted_names: list[str] = field(default_factory=list)
    skipped_names: list[str] = field(default_factory=list)
    failed_names: list[str] = field(default_factory=list)
    outcomes: list[tuple[Path, AdmitOutcome]] = field(default_factory=list)


def is_disambiguated_archive_name(name: str) -> bool:
    """True for ``foo (1).json``-style numeric originals archives."""
    return _DISAMBIG_STEM_RE.fullmatch(Path(name).stem) is not None


def list_originals_candidates(directory: Path) -> list[Path]:
    """Non-recursive list of regular transcript files eligible for admit."""
    if not directory.is_dir():
        return []
    out: list[Path] = []
    try:
        names = sorted(os.listdir(directory), key=str.lower)
    except OSError:
        return []
    for name in names:
        if name.startswith("."):
            continue
        if not extension_is_supported(name):
            continue
        if is_disambiguated_archive_name(name):
            continue
        path = directory / name
        try:
            if not path.is_file() or path.is_symlink():
                continue
        except OSError:
            continue
        out.append(path)
    return out


def admit_originals_file(path: Path) -> AdmitOutcome:
    """Admit one originals (or other host-written) transcript in place."""
    return admit_and_register(
        path,
        logical_basename=path.name,
        staging_cleanup=StagingCleanupPolicy.NEVER,
        allow_provenance_backfill=False,
    )


def admit_originals_files(
    paths: Sequence[Path],
    *,
    auto_name: bool | None = None,
    auto_link: bool | None = None,
) -> AdmitOriginalsStats:
    """Admit each path sequentially; already-managed files count as skipped."""
    stats = AdmitOriginalsStats()
    for path in paths:
        outcome = admit_originals_file(path)
        stats.outcomes.append((path, outcome))
        if outcome.kind in _SKIP_KINDS:
            stats.skipped += 1
            stats.skipped_names.append(path.name)
        elif outcome.kind in _SUCCESS_KINDS:
            stats.admitted += 1
            stats.admitted_names.append(path.name)
            _maybe_identify_after_admit(
                outcome,
                auto_name=auto_name,
                auto_link=auto_link,
            )
        else:
            stats.failed += 1
            stats.failed_names.append(f"{path.name}: {outcome.user_safe_detail}")
    return stats


def _maybe_identify_after_admit(
    outcome: AdmitOutcome,
    *,
    auto_name: bool | None,
    auto_link: bool | None,
) -> None:
    """Best-effort identify; never fail admit if identification errors."""
    if outcome.transcript_path is None:
        return
    try:
        from transcriptx.core.speaker_profiles.identify.service import (
            maybe_identify_admitted,
        )
        from transcriptx.core.speaker_profiles.identify.settings import (
            load_identify_settings,
        )

        settings = load_identify_settings()
        name_on = settings.auto_name if auto_name is None else bool(auto_name)
        link_on = settings.auto_link if auto_link is None else bool(auto_link)
        if auto_name is True and auto_link is None:
            link_on = True
        if not name_on and not link_on:
            return
        result = maybe_identify_admitted(
            outcome.transcript_path,
            auto_name=name_on,
            auto_link=link_on,
        )
        if result is None:
            return
        if result.error:
            print(
                f"  WARNING: identify {outcome.transcript_path.name}: {result.error}",
                file=sys.stderr,
                flush=True,
            )
            return
        print(
            f"  Identified {outcome.transcript_path.name}: "
            f"named={result.named_count} linked={result.linked_count}",
            flush=True,
        )
    except Exception as exc:
        print(
            f"  WARNING: identify skipped ({exc})",
            file=sys.stderr,
            flush=True,
        )


def run_admit_originals(
    directory: Path,
    *,
    only: Sequence[str] | None = None,
    dry_run: bool = False,
    auto_name: bool | None = None,
    auto_link: bool | None = None,
) -> int:
    """Scan *directory* and admit eligible files. Return process exit code."""
    if not directory.is_dir():
        print(f"ERROR: not a directory: {directory}", file=sys.stderr, flush=True)
        return 2

    candidates = list_originals_candidates(directory)
    if only:
        wanted = {name.lower() for name in only}
        candidates = [p for p in candidates if p.name.lower() in wanted]
        missing = wanted - {p.name.lower() for p in candidates}
        for name in sorted(missing):
            print(f"  Skipping (not found or ineligible): {name}", flush=True)

    print(flush=True)
    print("---", flush=True)
    print("Library admit (originals)", flush=True)
    print("---", flush=True)
    print(f"  Folder:     {directory}", flush=True)
    print(f"  Candidates: {len(candidates)}", flush=True)
    if dry_run:
        for path in candidates:
            print(f"  Would admit: {path.name}", flush=True)
        print("---", flush=True)
        return 0

    stats = admit_originals_files(
        candidates, auto_name=auto_name, auto_link=auto_link
    )
    for path, outcome in stats.outcomes:
        if outcome.kind in _SKIP_KINDS:
            print(f"  Skipping ({outcome.kind.value}): {path.name}", flush=True)
        elif outcome.kind in _SUCCESS_KINDS:
            print(f"  Admitted: {path.name} ({outcome.kind.value})", flush=True)
        else:
            print(
                f"ERROR: {path.name}: {outcome.user_safe_detail}",
                file=sys.stderr,
                flush=True,
            )
    print(f"  Admitted: {stats.admitted}", flush=True)
    print(f"  Skipped:  {stats.skipped}", flush=True)
    print(f"  Failed:   {stats.failed}", flush=True)
    print("---", flush=True)
    return 1 if stats.failed else 0
