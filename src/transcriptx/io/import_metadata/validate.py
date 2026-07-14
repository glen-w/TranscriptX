"""Managed-transcript validation gate (identity, wrong-path scan, cross-document checks).

Storage roots are read through the ``paths`` module at call time so monkeypatches
on ``transcriptx.io.import_metadata.paths`` govern both path derivation and
validation identity/scans.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from transcriptx.core.observability.perf import (
    observe_transcript_path,
    record_file_read,
)
from transcriptx.core.utils.logger import get_logger
from transcriptx.io.import_metadata import paths as sidecar_paths
from transcriptx.io.import_metadata.layout import (
    ImportSidecarLayout,
    resolve_import_sidecar_layout,
)
from transcriptx.io.import_metadata.persist import load_sidecar
from transcriptx.io.import_metadata.schema import (
    SIDECAR_SUFFIX,
    ManagedTranscriptCategory,
    ValidationResult,
    _validate_sidecar_schema,
)
from transcriptx.io.transcript_schema import validate_transcript_document

logger = get_logger()


def _transcript_relative_identity(transcript: Path) -> str:
    """Stable relative identity under transcripts root (posix)."""
    transcripts_root = Path(sidecar_paths.DIARISED_TRANSCRIPTS_DIR)
    try:
        return transcript.resolve().relative_to(transcripts_root.resolve()).as_posix()
    except (ValueError, OSError):
        try:
            return transcript.relative_to(transcripts_root).as_posix()
        except ValueError:
            return transcript.name


def _sidecar_claims_transcript(
    data: dict[str, Any], transcript: Path, *, candidate: Path
) -> bool:
    """True when sidecar content claims this transcript's identity."""
    if data.get("current_json_filename") != transcript.name:
        return False
    claimed_rel = data.get("transcript_relpath") or data.get("current_json_relpath")
    identity = _transcript_relative_identity(transcript)
    if isinstance(claimed_rel, str) and claimed_rel:
        return claimed_rel.replace("\\", "/") == identity

    metadata_root = Path(sidecar_paths.TRANSCRIPTS_METADATA_DIR)
    imports_root = metadata_root / "imports"
    try:
        rel = candidate.resolve().relative_to(imports_root.resolve())
    except (ValueError, OSError):
        # Flat / non-mirrored: basename claim is a conflict for this stem's
        # transcript (legacy duplicates are excluded via allowed_extra).
        return True
    name = rel.name
    if name.endswith(SIDECAR_SUFFIX):
        stem_name = name[: -len(SIDECAR_SUFFIX)] + ".json"
        inferred = (rel.parent / stem_name).as_posix()
        return inferred == identity
    return False


def _has_wrong_path_sidecar(
    transcript: Path,
    derived_sidecar: Path,
    *,
    allowed_extra: frozenset[Path] | None = None,
) -> bool:
    """Detect sidecars claiming this transcript's identity from wrong paths."""
    metadata_dir = Path(sidecar_paths.TRANSCRIPTS_METADATA_DIR)
    if not metadata_dir.exists():
        return False
    allowed = set(allowed_extra or ())
    try:
        derived_resolved = derived_sidecar.resolve()
    except OSError:
        derived_resolved = derived_sidecar
    allowed_resolved = {derived_resolved}
    for extra in allowed:
        try:
            allowed_resolved.add(extra.resolve())
        except OSError:
            allowed_resolved.add(extra)

    for candidate in metadata_dir.rglob(f"*{SIDECAR_SUFFIX}"):
        if candidate.name.startswith(".quarantine_"):
            continue
        try:
            cand_resolved = candidate.resolve()
        except OSError:
            cand_resolved = candidate
        if cand_resolved in allowed_resolved:
            continue
        try:
            data = load_sidecar(candidate)
        except Exception:
            continue
        if _sidecar_claims_transcript(data, transcript, candidate=candidate):
            return True
    return False


def validate_managed_transcript(transcript_path: str | Path) -> ValidationResult:
    transcript = Path(transcript_path)

    if not transcript.exists() or transcript.suffix.lower() != ".json":
        return ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.schema_error,
            message=f"Transcript not found or invalid extension: {transcript}",
            warnings=[],
        )

    # Finite mirrored/legacy resolution (same policy as rename planning).
    resolution = resolve_import_sidecar_layout(transcript)
    layout_warnings: list[str] = []
    if resolution.layout == ImportSidecarLayout.missing:
        return ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.missing_sidecar,
            message=resolution.block_message
            or f"Missing import sidecar for transcript: {transcript.name}",
            warnings=[],
        )
    if resolution.layout == ImportSidecarLayout.ambiguous:
        return ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.wrong_path,
            message=resolution.block_message
            or "Ambiguous import sidecar layout (mirrored and legacy differ)",
            warnings=[],
        )
    if resolution.warning:
        layout_warnings.append(resolution.warning)

    sidecar = resolution.authoritative_source
    assert sidecar is not None
    allowed_extra: frozenset[Path] | None = None
    if resolution.layout in (
        ImportSidecarLayout.both_identical,
        ImportSidecarLayout.legacy_flat,
    ):
        allowed_extra = frozenset({resolution.legacy_path})

    # Wrong-path scan uses mirrored path as the derived identity when present;
    # for legacy-only, allow the legacy path and still scan for other claimants.
    derived_for_scan = resolution.mirrored_path
    if _has_wrong_path_sidecar(
        transcript,
        derived_for_scan,
        allowed_extra=allowed_extra,
    ):
        return ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.wrong_path,
            message=(
                "Found conflicting sidecar outside derived path claiming this "
                f"transcript ({_transcript_relative_identity(transcript)!r})"
            ),
            warnings=[],
        )

    try:
        observe_transcript_path(transcript)
        record_file_read(
            transcript,
            section="validate_managed_transcript",
            purpose="transcript_validation",
        )
        with open(transcript, "r", encoding="utf-8") as handle:
            doc = json.load(handle)
    except Exception as exc:
        return ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.parse_error,
            message=f"Failed to parse transcript JSON: {exc}",
            warnings=[],
        )
    try:
        validate_transcript_document(doc)
    except Exception as exc:
        return ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.schema_error,
            message=f"Transcript schema validation failed: {exc}",
            warnings=[],
        )

    try:
        data = load_sidecar(sidecar)
    except Exception as exc:
        return ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.parse_error,
            message=f"Failed to parse sidecar JSON: {exc}",
            warnings=[],
        )
    sidecar_schema_result = _validate_sidecar_schema(data, transcript)
    if not sidecar_schema_result.ok:
        return sidecar_schema_result

    source = doc.get("source")
    if not isinstance(source, dict):
        return ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.schema_error,
            message="Transcript source section must be an object",
            warnings=[],
        )
    source_original_path = source.get("original_path")
    sidecar_archive_relpath = data.get("archived_original_relpath")
    if source_original_path != sidecar_archive_relpath:
        return ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.schema_error,
            message=(
                "source.original_path must equal sidecar archived_original_relpath "
                f"({source_original_path!r} != {sidecar_archive_relpath!r})"
            ),
            warnings=[],
        )

    warnings: list[str] = list(layout_warnings)
    archive_path = Path(sidecar_paths.DIARISED_TRANSCRIPTS_DIR) / str(
        sidecar_archive_relpath
    )
    if not archive_path.exists():
        warnings.append(ManagedTranscriptCategory.archive_missing.value)
    return ValidationResult(
        ok=True,
        category=ManagedTranscriptCategory.ok,
        message="Managed transcript is valid",
        warnings=warnings,
    )
