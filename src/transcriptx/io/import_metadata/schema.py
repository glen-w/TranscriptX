"""Import-metadata sidecar schema: constants, types, and schema validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

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
