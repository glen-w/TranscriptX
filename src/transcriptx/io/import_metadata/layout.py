"""Finite mirrored-vs-legacy import sidecar layout resolution (IO-owned policy)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ImportSidecarLayout(str, Enum):
    mirrored = "mirrored"
    legacy_flat = "legacy_flat"
    both_identical = "both_identical"
    ambiguous = "ambiguous"
    missing = "missing"


@dataclass(frozen=True)
class ImportSidecarResolution:
    layout: ImportSidecarLayout
    authoritative_source: Path | None
    mirrored_path: Path
    legacy_path: Path
    block_message: str = ""
    warning: str = ""


def resolve_import_sidecar_layout(transcript: Path) -> ImportSidecarResolution:
    """Fail-closed finite resolution of mirrored vs legacy flat import sidecars."""
    from transcriptx.io.import_metadata_sidecar import (
        legacy_flat_sidecar_path_for_transcript,
        mirrored_import_sidecar_path_for_transcript,
    )

    mirrored = mirrored_import_sidecar_path_for_transcript(transcript)
    legacy = legacy_flat_sidecar_path_for_transcript(transcript)
    mirrored_exists = mirrored.exists()
    legacy_exists = legacy.exists()

    if mirrored_exists and not legacy_exists:
        return ImportSidecarResolution(
            layout=ImportSidecarLayout.mirrored,
            authoritative_source=mirrored,
            mirrored_path=mirrored,
            legacy_path=legacy,
        )
    if legacy_exists and not mirrored_exists:
        return ImportSidecarResolution(
            layout=ImportSidecarLayout.legacy_flat,
            authoritative_source=legacy,
            mirrored_path=mirrored,
            legacy_path=legacy,
            warning="Legacy flat import sidecar will be migrated to mirrored layout",
        )
    if mirrored_exists and legacy_exists:
        try:
            if mirrored.read_bytes() == legacy.read_bytes():
                return ImportSidecarResolution(
                    layout=ImportSidecarLayout.both_identical,
                    authoritative_source=mirrored,
                    mirrored_path=mirrored,
                    legacy_path=legacy,
                    warning="Duplicate legacy flat sidecar will be quarantined",
                )
        except OSError as exc:
            return ImportSidecarResolution(
                layout=ImportSidecarLayout.ambiguous,
                authoritative_source=None,
                mirrored_path=mirrored,
                legacy_path=legacy,
                block_message=f"Could not compare import sidecars: {exc}",
            )
        return ImportSidecarResolution(
            layout=ImportSidecarLayout.ambiguous,
            authoritative_source=None,
            mirrored_path=mirrored,
            legacy_path=legacy,
            block_message=(
                "Ambiguous import sidecar layout: mirrored and legacy flat copies differ "
                f"({mirrored} vs {legacy})"
            ),
        )
    return ImportSidecarResolution(
        layout=ImportSidecarLayout.missing,
        authoritative_source=None,
        mirrored_path=mirrored,
        legacy_path=legacy,
        block_message=f"Missing import sidecar for transcript: {transcript.name}",
    )
