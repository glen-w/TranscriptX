"""Typed helpers for schema-epoch detection and remediation.

Internal / maintainer surface — not a public analysis CLI.
Never deletes recordings; default preserve managed transcripts.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from transcriptx.core.utils.schema_epoch import (
    CURRENT_SCHEMA_EPOCH,
    DataRootAssessment,
    DataRootStatus,
    assess_data_root,
    ensure_epoch_marker,
    write_epoch,
)

# Subtrees under data_root that are incompatible derived state by default.
# recordings/ and transcripts/ are never in this list.
DEFAULT_DERIVED_RESET_RELATIVE = (
    "outputs",
    "preprocessing",
    "cache",
    "state",
    "groups",
    "corrections",
    "speaker_profiles",
    "backups",
)


@dataclass(frozen=True)
class TranscriptInventoryItem:
    path: str
    relative_path: str
    size_bytes: int


@dataclass(frozen=True)
class TranscriptInventory:
    data_root: str
    transcripts_dir: str
    items: tuple[TranscriptInventoryItem, ...]
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_root": self.data_root,
            "transcripts_dir": self.transcripts_dir,
            "count": self.count,
            "items": [asdict(i) for i in self.items],
        }


@dataclass
class DerivedResetReport:
    """Report from a supported derived-state reset (no automatic deletion)."""

    data_root: str
    started_at: str
    finished_at: str = ""
    removed_paths: list[str] = field(default_factory=list)
    skipped_paths: list[str] = field(default_factory=list)
    preserved_paths: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    recordings_touched: bool = False
    transcripts_touched: bool = False
    epoch_written: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_managed_data_root(data_root: Path | None = None) -> DataRootAssessment:
    """Public typed assessment entry point."""
    return assess_data_root(data_root)


def initialize_empty_data_root(data_root: Path | None = None) -> DataRootAssessment:
    """Write epoch marker on empty roots; refuse occupied pre-epoch roots."""
    return ensure_epoch_marker(data_root, initialize_empty=True)


def inventory_compatible_transcripts(
    data_root: Path | None = None,
    *,
    transcripts_dir: Path | None = None,
) -> TranscriptInventory:
    """List JSON transcript artifacts under the managed transcripts tree.

    Does not modify any files. Used before optional export / reset.
    """
    from transcriptx.core.utils.paths import PATHS

    root = Path(data_root) if data_root is not None else Path(PATHS.data_dir)
    tdir = (
        Path(transcripts_dir)
        if transcripts_dir is not None
        else (
            Path(PATHS.transcripts_dir)
            if data_root is None
            else root / "transcripts"
        )
    )
    items: list[TranscriptInventoryItem] = []
    if tdir.is_dir():
        for path in sorted(tdir.rglob("*.json")):
            if not path.is_file():
                continue
            # Skip sidecars / metadata trees
            parts = {p.lower() for p in path.parts}
            if "metadata" in parts or path.name.endswith(".speaker_map.json"):
                continue
            if path.name.endswith(".import_meta.json"):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            try:
                rel = str(path.relative_to(tdir))
            except ValueError:
                rel = path.name
            items.append(
                TranscriptInventoryItem(
                    path=str(path),
                    relative_path=rel,
                    size_bytes=size,
                )
            )
    return TranscriptInventory(
        data_root=str(root),
        transcripts_dir=str(tdir),
        items=tuple(items),
        count=len(items),
    )


def export_transcript_inventory(
    inventory: TranscriptInventory,
    destination: Path,
) -> Path:
    """Write an inventory JSON report (paths only — not a full transcript copy)."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "kind": "transcriptx.schema_epoch_transcript_inventory.v1",
        "schema_epoch": CURRENT_SCHEMA_EPOCH,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **inventory.to_dict(),
    }
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return destination


def create_fresh_data_directory(
    new_data_root: Path,
    *,
    write_marker: bool = True,
) -> Path:
    """Create an empty epoch-1 data directory (recommended remediation).

    Does not modify any existing data root. Caller must point
    ``TRANSCRIPTX_DATA_DIR`` (or equivalent) at the new path.
    """
    root = Path(new_data_root)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(
            f"Refusing to initialize non-empty directory as fresh data root: {root}"
        )
    root.mkdir(parents=True, exist_ok=True)
    if write_marker:
        write_epoch(root, epoch=CURRENT_SCHEMA_EPOCH)
    return root


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def reset_incompatible_derived_state(
    data_root: Path,
    *,
    relative_targets: Sequence[str] = DEFAULT_DERIVED_RESET_RELATIVE,
    recordings_dir: Path | None = None,
    transcripts_dir: Path | None = None,
    write_epoch_marker: bool = True,
    dry_run: bool = False,
) -> DerivedResetReport:
    """Remove incompatible **derived** state under ``data_root``.

    Never touches recordings or transcripts trees. Caller must invoke
    explicitly — no automatic deletion.
    """
    from transcriptx.core.utils.paths import PATHS

    root = Path(data_root)
    started = datetime.now(timezone.utc).isoformat()
    report = DerivedResetReport(data_root=str(root), started_at=started)

    if recordings_dir is not None:
        rec = Path(recordings_dir)
    elif root.resolve() == Path(PATHS.data_dir).resolve():
        rec = Path(PATHS.recordings_dir)
    else:
        rec = root / "recordings"

    if transcripts_dir is not None:
        tr = Path(transcripts_dir)
    elif root.resolve() == Path(PATHS.data_dir).resolve():
        tr = Path(PATHS.transcripts_dir)
    else:
        tr = root / "transcripts"

    report.preserved_paths.extend([str(rec), str(tr)])

    for rel in relative_targets:
        target = root / rel
        if not target.exists():
            report.skipped_paths.append(str(target))
            continue
        if _is_under(target, rec) or target.resolve() == rec.resolve():
            report.errors.append(f"Refused to remove recordings path: {target}")
            report.recordings_touched = True
            continue
        if _is_under(target, tr) or target.resolve() == tr.resolve():
            report.errors.append(f"Refused to remove transcripts path: {target}")
            report.transcripts_touched = True
            continue
        if dry_run:
            report.removed_paths.append(str(target))
            continue
        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            report.removed_paths.append(str(target))
        except OSError as exc:
            report.errors.append(f"Failed to remove {target}: {exc}")

    if write_epoch_marker and not dry_run and not report.errors:
        try:
            write_epoch(root, epoch=CURRENT_SCHEMA_EPOCH)
            report.epoch_written = True
        except OSError as exc:
            report.errors.append(f"Failed to write epoch marker: {exc}")

    report.finished_at = datetime.now(timezone.utc).isoformat()
    # Safety invariant: we never intend to touch these
    if report.recordings_touched or report.transcripts_touched:
        # Flag only when refusal path fired; still never deleted them
        pass
    return report


def write_reset_report(report: DerivedResetReport, destination: Path) -> Path:
    """Persist a derived-state reset report as JSON."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "kind": "transcriptx.schema_epoch_reset_report.v1",
        "schema_epoch": CURRENT_SCHEMA_EPOCH,
        **report.to_dict(),
    }
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return destination


def remediation_copy_for(assessment: DataRootAssessment) -> str:
    """User-facing explanation for an incompatible root."""
    root = assessment.data_root
    if assessment.status == DataRootStatus.MISSING_MARKER:
        return (
            f"The managed data directory `{root}` has content but no schema-epoch "
            f"marker. This store is from before public schema epoch "
            f"{CURRENT_SCHEMA_EPOCH} (or is unmarked). Principal analysis work is "
            f"blocked until you remediate."
        )
    if assessment.status == DataRootStatus.PRE_EPOCH:
        return (
            f"The managed data directory `{root}` is schema epoch "
            f"{assessment.epoch}, but this package requires epoch "
            f"{CURRENT_SCHEMA_EPOCH}. Principal analysis work is blocked."
        )
    if assessment.status == DataRootStatus.FOREIGN:
        return (
            f"The managed data directory `{root}` is not compatible with this "
            f"package (epoch {assessment.epoch!r}; supports "
            f"{CURRENT_SCHEMA_EPOCH}). {assessment.detail}"
        )
    return assessment.detail or f"Data root `{root}` needs attention."


__all__ = [
    "DEFAULT_DERIVED_RESET_RELATIVE",
    "DerivedResetReport",
    "TranscriptInventory",
    "TranscriptInventoryItem",
    "assess_managed_data_root",
    "create_fresh_data_directory",
    "export_transcript_inventory",
    "initialize_empty_data_root",
    "inventory_compatible_transcripts",
    "remediation_copy_for",
    "reset_incompatible_derived_state",
    "write_reset_report",
]
