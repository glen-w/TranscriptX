from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import (
    DIARISED_TRANSCRIPTS_DIR,
    TRANSCRIPTS_METADATA_DIR,
)
from transcriptx.core.utils.rename.io_atomic import (
    write_json_atomic as _write_json_atomic,
)
from transcriptx.io.transcript_schema import validate_transcript_document
from transcriptx.core.observability.perf import (
    observe_transcript_path,
    record_file_read,
)

logger = get_logger()

SIDECAR_SCHEMA_VERSION = 1
SIDECAR_SUFFIX = ".import_meta.json"


class ManagedTranscriptCategory(str, Enum):
    ok = "ok"
    missing_sidecar = "missing_sidecar"
    parse_error = "parse_error"
    schema_error = "schema_error"
    filename_mismatch = "filename_mismatch"
    wrong_path = "wrong_path"
    archive_missing = "archive_missing"


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    category: ManagedTranscriptCategory
    message: str
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ImportMetadata:
    import_id: str
    imported_at: str
    adapter_source_id: str
    source_upload_basename: str
    archived_original_relpath: str
    current_json_filename: str
    rename_history: list[dict[str, str]]
    schema_version: int = SIDECAR_SCHEMA_VERSION


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


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Crash-safe staged JSON write (fsync file + best-effort parent dir)."""
    _write_json_atomic(path, payload, indent=2)


def compute_rename_history_payload(
    sidecar_path: str | Path,
    *,
    old_filename: str,
    new_filename: str,
    at_iso: str,
) -> dict[str, Any]:
    """Validate sidecar and return the mutated payload (no write)."""
    sidecar = Path(sidecar_path)
    payload = load_sidecar(sidecar)
    history = payload.get("rename_history")
    if not isinstance(history, list):
        raise ValueError("rename_history must be a list")
    history = list(history)
    history.append(
        {
            "at": at_iso,
            "from_filename": old_filename,
            "to_filename": new_filename,
        }
    )
    payload = dict(payload)
    payload["rename_history"] = history
    payload["current_json_filename"] = new_filename
    return payload


def load_sidecar(path: Path) -> dict[str, Any]:
    record_file_read(path, section="load_sidecar", purpose="metadata_extraction")
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Sidecar root must be an object")
    return data


def _required_sidecar_fields(data: dict[str, Any]) -> list[str]:
    required = [
        "schema_version",
        "import_id",
        "imported_at",
        "adapter_source_id",
        "source_upload_basename",
        "archived_original_relpath",
        "current_json_filename",
        "rename_history",
    ]
    return [k for k in required if k not in data]


def _validate_sidecar_schema(
    data: dict[str, Any], transcript: Path
) -> ValidationResult:
    missing = _required_sidecar_fields(data)
    if missing:
        return ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.schema_error,
            message=f"Missing sidecar fields: {', '.join(missing)}",
            warnings=[],
        )
    if data.get("schema_version") != SIDECAR_SCHEMA_VERSION:
        return ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.schema_error,
            message=f"Unsupported sidecar schema_version: {data.get('schema_version')}",
            warnings=[],
        )
    if data.get("current_json_filename") != transcript.name:
        return ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.filename_mismatch,
            message=(
                f"current_json_filename mismatch: {data.get('current_json_filename')!r} "
                f"!= {transcript.name!r}"
            ),
            warnings=[],
        )
    if not isinstance(data.get("rename_history"), list):
        return ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.schema_error,
            message="rename_history must be a list",
            warnings=[],
        )
    return ValidationResult(
        ok=True,
        category=ManagedTranscriptCategory.ok,
        message="Sidecar schema is valid",
        warnings=[],
    )


def _transcript_relative_identity(transcript: Path) -> str:
    """Stable relative identity under transcripts root (posix)."""
    transcripts_root = Path(DIARISED_TRANSCRIPTS_DIR)
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

    metadata_root = Path(TRANSCRIPTS_METADATA_DIR)
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
    metadata_dir = Path(TRANSCRIPTS_METADATA_DIR)
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
    from transcriptx.core.utils.rename.sidecars import (
        ImportSidecarLayout,
        resolve_import_sidecar_layout,
    )

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
    archive_path = Path(DIARISED_TRANSCRIPTS_DIR) / str(sidecar_archive_relpath)
    if not archive_path.exists():
        warnings.append(ManagedTranscriptCategory.archive_missing.value)
    return ValidationResult(
        ok=True,
        category=ManagedTranscriptCategory.ok,
        message="Managed transcript is valid",
        warnings=warnings,
    )


def build_initial_sidecar(
    *,
    import_id: str,
    imported_at: str,
    adapter_source_id: str,
    source_upload_basename: str,
    archived_original_relpath: str,
    current_json_filename: str,
) -> dict[str, Any]:
    return {
        "schema_version": SIDECAR_SCHEMA_VERSION,
        "import_id": import_id,
        "imported_at": imported_at,
        "adapter_source_id": adapter_source_id,
        "source_upload_basename": source_upload_basename,
        "archived_original_relpath": archived_original_relpath,
        "current_json_filename": current_json_filename,
        "rename_history": [],
    }


def write_initial_sidecar(
    transcript_path: str | Path,
    *,
    import_id: str | None = None,
    imported_at: str,
    adapter_source_id: str,
    source_upload_basename: str,
    archived_original_relpath: str,
) -> Path:
    transcript = Path(transcript_path)
    sidecar = sidecar_path_for_transcript(transcript)
    payload = build_initial_sidecar(
        import_id=import_id or str(uuid.uuid4()),
        imported_at=imported_at,
        adapter_source_id=adapter_source_id,
        source_upload_basename=source_upload_basename,
        archived_original_relpath=archived_original_relpath,
        current_json_filename=transcript.name,
    )
    write_json_atomic(sidecar, payload)
    return sidecar


def append_rename_history(
    *,
    sidecar_path: str | Path,
    old_filename: str,
    new_filename: str,
    at_iso: str,
) -> None:
    payload = compute_rename_history_payload(
        sidecar_path,
        old_filename=old_filename,
        new_filename=new_filename,
        at_iso=at_iso,
    )
    write_json_atomic(Path(sidecar_path), payload)
