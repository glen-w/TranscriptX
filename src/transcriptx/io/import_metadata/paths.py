"""Import-metadata sidecar path derivation.

Module-level ``DIARISED_TRANSCRIPTS_DIR`` / ``TRANSCRIPTS_METADATA_DIR`` are the
canonical monkeypatch surface for storage roots in tests; all sidecar path and
identity derivation reads these globals at call time.
"""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.utils.paths import (
    DIARISED_TRANSCRIPTS_DIR,
    TRANSCRIPTS_METADATA_DIR,
)
from transcriptx.io.import_metadata.schema import SIDECAR_SUFFIX

__all__ = [
    "DIARISED_TRANSCRIPTS_DIR",
    "TRANSCRIPTS_METADATA_DIR",
    "mirrored_import_sidecar_path_for_transcript",
    "legacy_flat_sidecar_path_for_transcript",
    "sidecar_path_for_transcript",
    "find_existing_import_sidecar",
]


def mirrored_import_sidecar_path_for_transcript(transcript_path: str | Path) -> Path:
    """Authoritative mirrored path: metadata/imports/<transcript-rel>.import_meta.json.

    Uses module-level ``DIARISED_TRANSCRIPTS_DIR`` / ``TRANSCRIPTS_METADATA_DIR`` so tests
    can monkeypatch storage roots without replacing PATHS.
    """
    transcript = Path(transcript_path)
    transcripts_root = Path(DIARISED_TRANSCRIPTS_DIR)
    metadata_root = Path(TRANSCRIPTS_METADATA_DIR)
    try:
        rel = transcript.resolve().relative_to(transcripts_root.resolve())
    except (ValueError, OSError):
        try:
            rel = transcript.relative_to(transcripts_root)
        except ValueError:
            rel = Path(transcript.name)
    if rel.suffix:
        base = rel.with_suffix(SIDECAR_SUFFIX)
    else:
        base = rel.parent / (rel.name + SIDECAR_SUFFIX)
    return metadata_root / "imports" / base


def legacy_flat_sidecar_path_for_transcript(transcript_path: str | Path) -> Path:
    """Legacy flat layout (to be migrated away): metadata/<stem>.import_meta.json."""
    transcript = Path(transcript_path)
    return Path(TRANSCRIPTS_METADATA_DIR) / f"{transcript.stem}{SIDECAR_SUFFIX}"


def sidecar_path_for_transcript(transcript_path: str | Path) -> Path:
    """Return the authoritative (mirrored) import-metadata sidecar path."""
    return mirrored_import_sidecar_path_for_transcript(transcript_path)


def find_existing_import_sidecar(transcript_path: str | Path) -> Path | None:
    """Locate an existing sidecar: mirrored preferred, else legacy flat (finite)."""
    mirrored = mirrored_import_sidecar_path_for_transcript(transcript_path)
    if mirrored.exists():
        return mirrored
    legacy = legacy_flat_sidecar_path_for_transcript(transcript_path)
    if legacy.exists():
        return legacy
    return None
