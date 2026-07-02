from __future__ import annotations

import json
import os
import tempfile
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


def sidecar_path_for_transcript(transcript_path: str | Path) -> Path:
    transcript = Path(transcript_path)
    return Path(TRANSCRIPTS_METADATA_DIR) / f"{transcript.stem}{SIDECAR_SUFFIX}"


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temp = Path(temp_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temp), str(path))
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


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


def _has_wrong_path_sidecar(transcript: Path, derived_sidecar: Path) -> bool:
    """Detect sidecars outside derived path claiming this transcript filename."""
    metadata_dir = Path(TRANSCRIPTS_METADATA_DIR)
    if not metadata_dir.exists():
        return False
    for candidate in metadata_dir.glob(f"*{SIDECAR_SUFFIX}"):
        if candidate.resolve() == derived_sidecar.resolve():
            continue
        try:
            data = load_sidecar(candidate)
        except Exception:
            continue
        if data.get("current_json_filename") == transcript.name:
            return True
    return False


def validate_managed_transcript(transcript_path: str | Path) -> ValidationResult:
    transcript = Path(transcript_path)
    sidecar = sidecar_path_for_transcript(transcript)

    if not transcript.exists() or transcript.suffix.lower() != ".json":
        return ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.schema_error,
            message=f"Transcript not found or invalid extension: {transcript}",
            warnings=[],
        )
    if not sidecar.exists():
        return ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.missing_sidecar,
            message=f"Missing import sidecar for transcript: {transcript.name}",
            warnings=[],
        )
    if _has_wrong_path_sidecar(transcript, sidecar):
        return ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.wrong_path,
            message=(
                "Found conflicting sidecar outside derived path claiming "
                f"current_json_filename={transcript.name!r}"
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

    warnings: list[str] = []
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
    sidecar = Path(sidecar_path)
    payload = load_sidecar(sidecar)
    history = payload.get("rename_history")
    if not isinstance(history, list):
        raise ValueError("rename_history must be a list")
    history.append(
        {
            "at": at_iso,
            "from_filename": old_filename,
            "to_filename": new_filename,
        }
    )
    payload["rename_history"] = history
    payload["current_json_filename"] = new_filename
    write_json_atomic(sidecar, payload)
