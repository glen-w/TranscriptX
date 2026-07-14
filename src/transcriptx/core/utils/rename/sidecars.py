"""Managed sidecar planner and import-metadata path resolution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from transcriptx.core.utils.logger import get_logger
from transcriptx.io.import_metadata.layout import (  # noqa: F401 — re-exported for compat
    ImportSidecarLayout,
    ImportSidecarResolution,
    resolve_import_sidecar_layout,
)
from transcriptx.io.import_metadata_sidecar import (
    compute_rename_history_payload,
    legacy_flat_sidecar_path_for_transcript,
    mirrored_import_sidecar_path_for_transcript,
)
from transcriptx.io.speaker_map_resolver import (
    sidecar_path_for as speaker_map_sidecar_path,
)

logger = get_logger()


def unique_quarantine_path(legacy: Path) -> Path:
    """Unique quarantine target for a legacy flat sidecar (rollback-friendly rename)."""
    return legacy.parent / f".quarantine_{uuid.uuid4().hex}_{legacy.name}"


class SidecarKind(str, Enum):
    import_metadata = "import_metadata"
    speaker_map = "speaker_map"


@dataclass(frozen=True)
class SidecarMove:
    kind: SidecarKind
    source: Path
    dest: Path
    description: str
    staged_payload: dict[str, Any] | None = None
    quarantine_legacy: Path | None = None
    delete_legacy: Path | None = None


def plan_managed_sidecar_moves(
    old_transcript: Path,
    new_transcript: Path,
    *,
    rename_history_at_iso: str,
) -> tuple[SidecarMove, ...] | str:
    """Plan all managed sidecar moves.

    Returns a tuple of SidecarMove on success, or a block message string on failure.
    """
    old_transcript = Path(old_transcript)
    new_transcript = Path(new_transcript)
    moves: list[SidecarMove] = []

    resolution = resolve_import_sidecar_layout(old_transcript)
    if resolution.layout == ImportSidecarLayout.ambiguous:
        return resolution.block_message
    if resolution.layout == ImportSidecarLayout.missing:
        return resolution.block_message

    new_mirrored = mirrored_import_sidecar_path_for_transcript(new_transcript)
    new_legacy = legacy_flat_sidecar_path_for_transcript(new_transcript)

    if new_legacy.exists() and new_legacy != resolution.legacy_path:
        return (
            f"Rename blocked: target legacy import sidecar already exists: {new_legacy}"
        )

    source = resolution.authoritative_source
    assert source is not None

    if new_mirrored.exists() and new_mirrored != source:
        # Same content duplicate on new path is ok only for case-only/self; otherwise block
        if new_mirrored.resolve() != source.resolve():
            return (
                "Rename blocked: target import sidecar already exists: "
                f"{new_mirrored}"
            )

    old_filename = old_transcript.name
    new_filename = new_transcript.name
    staged_payload = compute_rename_history_payload(
        source,
        old_filename=old_filename,
        new_filename=new_filename,
        at_iso=rename_history_at_iso,
    )

    if source != new_mirrored:
        moves.append(
            SidecarMove(
                kind=SidecarKind.import_metadata,
                source=source,
                dest=new_mirrored,
                description=(
                    f"Rename/migrate import sidecar: {source} -> {new_mirrored}"
                ),
                staged_payload=staged_payload,
                quarantine_legacy=(
                    resolution.legacy_path
                    if resolution.layout == ImportSidecarLayout.both_identical
                    else None
                ),
            )
        )
    else:
        moves.append(
            SidecarMove(
                kind=SidecarKind.import_metadata,
                source=source,
                dest=new_mirrored,
                description="Update import sidecar rename history (path unchanged)",
                staged_payload=staged_payload,
                quarantine_legacy=(
                    resolution.legacy_path
                    if resolution.layout == ImportSidecarLayout.both_identical
                    else None
                ),
            )
        )

    old_speaker = speaker_map_sidecar_path(old_transcript)
    new_speaker = speaker_map_sidecar_path(new_transcript)
    if old_speaker.exists() and old_speaker != new_speaker:
        if new_speaker.exists():
            return f"Rename blocked: target speaker map already exists: {new_speaker}"
        moves.append(
            SidecarMove(
                kind=SidecarKind.speaker_map,
                source=old_speaker,
                dest=new_speaker,
                description=(
                    f"Rename speaker map sidecar: {old_speaker.name} -> {new_speaker.name}"
                ),
            )
        )

    return tuple(moves)
