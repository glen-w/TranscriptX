"""Public schema-epoch marker for managed data roots.

Epoch-1 is the sole public persisted schema generation for 0.9.3+.
Pre-epoch or unmarked occupied roots fail closed; callers surface remediation
UX (GUI / typed helper) — never silent adapters or automatic deletion.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from transcriptx.io.atomic_json import write_json_atomic

# Public integer epoch stamped at managed data roots.
CURRENT_SCHEMA_EPOCH = 1

MARKER_FILENAME = "schema_epoch.json"
MARKER_KIND = "transcriptx.schema_epoch"


class DataRootStatus(str, Enum):
    """Assessment of a managed data root relative to the public schema epoch."""

    COMPATIBLE = "compatible"
    MISSING_MARKER = "missing_marker"
    PRE_EPOCH = "pre_epoch"
    FOREIGN = "foreign"
    EMPTY = "empty"


@dataclass(frozen=True)
class DataRootAssessment:
    """Result of assessing a managed data directory."""

    status: DataRootStatus
    data_root: Path
    marker_path: Path
    epoch: int | None = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status in (DataRootStatus.COMPATIBLE, DataRootStatus.EMPTY)


def marker_path_for(data_root: Path) -> Path:
    """Return the canonical epoch marker path under ``data_root``."""
    return Path(data_root) / MARKER_FILENAME


def read_epoch(data_root: Path) -> int | None:
    """Read the integer epoch from the marker, or None if missing/unreadable."""
    path = marker_path_for(data_root)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    raw = payload.get("schema_epoch", payload.get("epoch"))
    if isinstance(raw, bool) or not isinstance(raw, int):
        return None
    return raw


def write_epoch(
    data_root: Path,
    *,
    epoch: int = CURRENT_SCHEMA_EPOCH,
) -> Path:
    """Atomically write the epoch marker under ``data_root``.

    Creates ``data_root`` if needed. Does not delete or modify other contents.
    """
    root = Path(data_root)
    root.mkdir(parents=True, exist_ok=True)
    path = marker_path_for(root)
    payload: dict[str, Any] = {
        "kind": MARKER_KIND,
        "schema_epoch": int(epoch),
    }
    write_json_atomic(path, payload)
    return path


def _data_root_looks_occupied(data_root: Path) -> bool:
    """True when the root has non-marker content that suggests a store."""
    root = Path(data_root)
    if not root.is_dir():
        return False
    try:
        entries = list(root.iterdir())
    except OSError:
        return False
    for entry in entries:
        if entry.name == MARKER_FILENAME:
            continue
        if entry.name.startswith("."):
            continue
        return True
    return False


def assess_data_root(data_root: Path | None = None) -> DataRootAssessment:
    """Classify a managed data root for epoch-1 compatibility.

    Statuses:
    - ``compatible``: marker present with ``CURRENT_SCHEMA_EPOCH``
    - ``empty``: root missing or empty (safe to initialize)
    - ``missing_marker``: occupied root without a marker (pre-epoch / unmarked)
    - ``pre_epoch``: marker present with epoch < current
    - ``foreign``: marker present with epoch > current or unreadable shape
    """
    from transcriptx.core.utils.paths import PATHS

    root = Path(data_root) if data_root is not None else Path(PATHS.data_dir)
    marker = marker_path_for(root)

    if not root.exists():
        return DataRootAssessment(
            status=DataRootStatus.EMPTY,
            data_root=root,
            marker_path=marker,
            detail="Data root does not exist yet.",
        )

    if not root.is_dir():
        return DataRootAssessment(
            status=DataRootStatus.FOREIGN,
            data_root=root,
            marker_path=marker,
            detail=f"Data root path is not a directory: {root}",
        )

    epoch = read_epoch(root)
    if epoch is None:
        if not _data_root_looks_occupied(root):
            return DataRootAssessment(
                status=DataRootStatus.EMPTY,
                data_root=root,
                marker_path=marker,
                detail="Data root is empty; ready for epoch initialization.",
            )
        return DataRootAssessment(
            status=DataRootStatus.MISSING_MARKER,
            data_root=root,
            marker_path=marker,
            detail=(
                f"Managed data root {root} has content but no "
                f"{MARKER_FILENAME} marker (pre-epoch or unmarked store)."
            ),
        )

    if epoch == CURRENT_SCHEMA_EPOCH:
        return DataRootAssessment(
            status=DataRootStatus.COMPATIBLE,
            data_root=root,
            marker_path=marker,
            epoch=epoch,
            detail=f"Data root is schema epoch {epoch}.",
        )

    if epoch < CURRENT_SCHEMA_EPOCH:
        return DataRootAssessment(
            status=DataRootStatus.PRE_EPOCH,
            data_root=root,
            marker_path=marker,
            epoch=epoch,
            detail=(
                f"Data root schema epoch {epoch} is older than "
                f"required epoch {CURRENT_SCHEMA_EPOCH}."
            ),
        )

    return DataRootAssessment(
        status=DataRootStatus.FOREIGN,
        data_root=root,
        marker_path=marker,
        epoch=epoch,
        detail=(
            f"Data root schema epoch {epoch} is newer than this package "
            f"(supports epoch {CURRENT_SCHEMA_EPOCH})."
        ),
    )


def ensure_epoch_marker(
    data_root: Path | None = None,
    *,
    initialize_empty: bool = True,
) -> DataRootAssessment:
    """Assess the root; optionally write the marker on empty roots.

    Returns the (possibly updated) assessment. Never writes over an occupied
    pre-epoch or foreign root.
    """
    from transcriptx.core.utils.paths import PATHS

    root = Path(data_root) if data_root is not None else Path(PATHS.data_dir)
    assessment = assess_data_root(root)
    if assessment.status == DataRootStatus.EMPTY and initialize_empty:
        write_epoch(root, epoch=CURRENT_SCHEMA_EPOCH)
        return assess_data_root(root)
    return assessment


def require_compatible_data_root(data_root: Path | None = None) -> DataRootAssessment:
    """Return a compatible assessment or raise ``SchemaEpochError``."""
    assessment = ensure_epoch_marker(data_root, initialize_empty=True)
    if assessment.ok or assessment.status == DataRootStatus.COMPATIBLE:
        return assessment
    raise SchemaEpochError(assessment)


class SchemaEpochError(RuntimeError):
    """Raised when a managed data root is incompatible with the public epoch."""

    def __init__(self, assessment: DataRootAssessment) -> None:
        self.assessment = assessment
        super().__init__(
            f"Incompatible schema epoch for data root {assessment.data_root}: "
            f"{assessment.status.value}. {assessment.detail}"
        )


__all__ = [
    "CURRENT_SCHEMA_EPOCH",
    "MARKER_FILENAME",
    "MARKER_KIND",
    "DataRootAssessment",
    "DataRootStatus",
    "SchemaEpochError",
    "assess_data_root",
    "ensure_epoch_marker",
    "marker_path_for",
    "read_epoch",
    "require_compatible_data_root",
    "write_epoch",
]
