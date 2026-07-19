"""Pure admission primitives shared by uploader, folder scan, and managed workflow.

This module must not import admit_and_register, slug_manager, or web UI code.
"""

from __future__ import annotations

import json
import os
import posixpath
import re
import stat
import unicodedata
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from transcriptx.core.utils.paths import (
    DIARISED_TRANSCRIPTS_DIR,
    TRANSCRIPTS_IMPORTS_DIR,
)
from transcriptx.io.import_metadata_sidecar import sidecar_path_for_transcript
from transcriptx.io.transcript_schema import validate_transcript_document

ADMISSION_POLICY_VERSION = 1
SCAN_HANDLE_SCHEMA_VERSION = 1

DEFAULT_MAX_IMPORT_FILE_BYTES = 100 * 1024 * 1024  # 100 MiB
DEFAULT_MAX_FOLDER_IMPORT_CANDIDATES = 500

SUPPORTED_IMPORT_EXTENSIONS: frozenset[str] = frozenset(
    {".json", ".srt", ".vtt", ".txt", ".html", ".htm"}
)

# Streamlit file_uploader ``type`` list (no dots).
SUPPORTED_IMPORT_UPLOAD_TYPES: tuple[str, ...] = tuple(
    sorted(ext.lstrip(".") for ext in SUPPORTED_IMPORT_EXTENSIONS)
)

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


class ManagedArtifactState(str, Enum):
    ABSENT = "absent"
    ALREADY_MANAGED = "already_managed"
    INCOMPLETE_REPAIRABLE = "incomplete_repairable"
    INCOMPLETE_UNREPAIRABLE = "incomplete_unrepairable"
    INCONSISTENT = "inconsistent"


@dataclass(frozen=True)
class CanonicalTarget:
    """Derived managed target paths for an upload basename."""

    archive_basename: str
    display_stem: str
    conflict_key: str
    target_json: Path
    sidecar_path: Path


@dataclass(frozen=True)
class ManagedStateInspection:
    state: ManagedArtifactState
    target_json: Path
    sidecar_path: Path
    archived_original_relpath: str | None = None
    detail: str = ""


class AdmissionError(ValueError):
    """User-safe admission validation error."""


def get_max_import_file_bytes() -> int:
    raw = os.environ.get("TRANSCRIPTX_FOLDER_IMPORT_MAX_FILE_BYTES")
    if raw is None or not str(raw).strip():
        return DEFAULT_MAX_IMPORT_FILE_BYTES
    try:
        value = int(str(raw).strip(), 10)
    except ValueError as exc:
        raise AdmissionError(
            "TRANSCRIPTX_FOLDER_IMPORT_MAX_FILE_BYTES must be an integer."
        ) from exc
    if value < 1:
        raise AdmissionError(
            "TRANSCRIPTX_FOLDER_IMPORT_MAX_FILE_BYTES must be at least 1."
        )
    return value


def get_max_folder_import_candidates() -> int:
    raw = os.environ.get("TRANSCRIPTX_FOLDER_IMPORT_MAX_CANDIDATES")
    if raw is None or not str(raw).strip():
        return DEFAULT_MAX_FOLDER_IMPORT_CANDIDATES
    try:
        value = int(str(raw).strip(), 10)
    except ValueError as exc:
        raise AdmissionError(
            "TRANSCRIPTX_FOLDER_IMPORT_MAX_CANDIDATES must be an integer."
        ) from exc
    if value < 1:
        raise AdmissionError(
            "TRANSCRIPTX_FOLDER_IMPORT_MAX_CANDIDATES must be at least 1."
        )
    return value


def assert_within_import_size_limit(
    byte_size: int, *, max_bytes: int | None = None
) -> None:
    limit = get_max_import_file_bytes() if max_bytes is None else max_bytes
    if byte_size < 0:
        raise AdmissionError("File size cannot be negative.")
    if byte_size > limit:
        raise AdmissionError(
            f"File is too large ({byte_size} bytes). Limit is {limit} bytes."
        )


def extension_is_supported(path: str | Path) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in SUPPORTED_IMPORT_EXTENSIONS


def sanitize_upload_basename(raw_name: str | None) -> str:
    """Return a safe single-segment basename for archive/stem derivation."""
    if raw_name is None:
        raise AdmissionError("Upload filename is missing.")
    name = str(raw_name).replace("\\", "/").strip()
    if not name:
        raise AdmissionError("Upload filename is empty.")
    parts = [p for p in name.split("/") if p not in {"", "."}]
    if any(p == ".." for p in parts):
        raise AdmissionError("Upload filename must not contain parent-directory segments.")
    name = parts[-1] if parts else ""
    name = unicodedata.normalize("NFC", name)
    if _CONTROL_CHARS.search(name):
        raise AdmissionError("Upload filename contains control characters.")
    if name in {".", ".."} or not name.strip("."):
        raise AdmissionError("Upload filename is not a valid file name.")
    if "/" in name or "\\" in name:
        raise AdmissionError("Upload filename must not contain path separators.")
    return name


def normalize_conflict_stem(stem: str) -> str:
    """Case-folded NFC stem used for duplicate-stem grouping and target keys."""
    return unicodedata.normalize("NFC", stem).casefold()


def derive_canonical_target(
    logical_basename: str,
    *,
    transcripts_dir: str | Path | None = None,
) -> CanonicalTarget:
    basename = sanitize_upload_basename(logical_basename)
    path = Path(basename)
    if not extension_is_supported(path):
        raise AdmissionError(
            f"Unsupported transcript extension: {path.suffix or '(none)'}."
        )
    display_stem = path.stem
    if not display_stem or display_stem in {".", ".."}:
        raise AdmissionError("Upload filename has an empty stem.")
    conflict_key = normalize_conflict_stem(display_stem)
    if not conflict_key:
        raise AdmissionError("Upload filename stem is empty after normalisation.")

    root = Path(transcripts_dir) if transcripts_dir is not None else Path(
        DIARISED_TRANSCRIPTS_DIR
    )
    # On-disk JSON uses the sanitised display stem (preserves original casing).
    target_json = root / f"{display_stem}.json"
    return CanonicalTarget(
        archive_basename=basename,
        display_stem=display_stem,
        conflict_key=conflict_key,
        target_json=target_json,
        sidecar_path=sidecar_path_for_transcript(target_json),
    )


def _source_object_from_document(doc: dict[str, Any]) -> dict[str, Any]:
    raw = doc.get("source")
    return raw if isinstance(raw, dict) else {}


def validate_safe_originals_relpath(
    rel: str, *, output_dir: Path
) -> tuple[str, Path]:
    """Return normalised originals/ relpath and absolute archive path, or raise."""
    if not rel or not str(rel).strip():
        raise AdmissionError("source.original_path is missing.")
    normalized = posixpath.normpath(str(rel).replace("\\", "/"))
    if normalized in {".", ".."} or normalized.startswith("../"):
        raise AdmissionError("source.original_path is not a safe relative path.")
    if not normalized.startswith("originals/"):
        raise AdmissionError("source.original_path must be under originals/.")
    archive_path = output_dir / normalized
    try:
        if not archive_path.is_file():
            raise AdmissionError("source.original_path archive file is missing.")
    except OSError as exc:
        raise AdmissionError(
            "source.original_path archive file is not readable."
        ) from exc
    return normalized, archive_path


def _load_json_object(path: Path) -> dict[str, Any] | None:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            doc = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def inspect_managed_artifact_state(
    target_json: Path,
    *,
    sidecar_path: Path | None = None,
    transcripts_dir: str | Path | None = None,
) -> ManagedStateInspection:
    """Inspect JSON/sidecar pair without registration side effects."""
    target = Path(target_json)
    sidecar = Path(sidecar_path) if sidecar_path is not None else sidecar_path_for_transcript(
        target
    )
    output_dir = (
        Path(transcripts_dir)
        if transcripts_dir is not None
        else Path(DIARISED_TRANSCRIPTS_DIR)
    )

    json_exists = False
    sidecar_exists = False
    try:
        json_exists = target.is_file()
    except OSError:
        json_exists = False
    try:
        sidecar_exists = sidecar.is_file()
    except OSError:
        sidecar_exists = False

    if not json_exists and not sidecar_exists:
        return ManagedStateInspection(
            state=ManagedArtifactState.ABSENT,
            target_json=target,
            sidecar_path=sidecar,
        )
    if sidecar_exists and not json_exists:
        return ManagedStateInspection(
            state=ManagedArtifactState.INCONSISTENT,
            target_json=target,
            sidecar_path=sidecar,
            detail="Import sidecar exists without canonical JSON.",
        )
    if json_exists and sidecar_exists:
        return ManagedStateInspection(
            state=ManagedArtifactState.ALREADY_MANAGED,
            target_json=target,
            sidecar_path=sidecar,
        )

    # JSON without sidecar — repairable only with valid schema + safe originals.
    doc = _load_json_object(target)
    if doc is None:
        return ManagedStateInspection(
            state=ManagedArtifactState.INCOMPLETE_UNREPAIRABLE,
            target_json=target,
            sidecar_path=sidecar,
            detail="Canonical JSON is missing or not a valid JSON object.",
        )
    try:
        validate_transcript_document(doc, label=str(target))
    except ValueError as exc:
        return ManagedStateInspection(
            state=ManagedArtifactState.INCOMPLETE_UNREPAIRABLE,
            target_json=target,
            sidecar_path=sidecar,
            detail=f"Canonical JSON failed schema validation: {exc}",
        )
    source = _source_object_from_document(doc)
    rel = str(source.get("original_path") or "")
    try:
        normalized, _archive = validate_safe_originals_relpath(rel, output_dir=output_dir)
    except AdmissionError as exc:
        return ManagedStateInspection(
            state=ManagedArtifactState.INCOMPLETE_UNREPAIRABLE,
            target_json=target,
            sidecar_path=sidecar,
            detail=str(exc),
        )
    return ManagedStateInspection(
        state=ManagedArtifactState.INCOMPLETE_REPAIRABLE,
        target_json=target,
        sidecar_path=sidecar,
        archived_original_relpath=normalized,
        detail="Canonical JSON present; import sidecar missing.",
    )


def is_under_directory(path: Path, root: Path) -> bool:
    """True when resolved path is root or a descendant of root."""
    try:
        resolved = path.resolve()
        root_resolved = root.resolve()
    except OSError:
        return False
    try:
        resolved.relative_to(root_resolved)
        return True
    except ValueError:
        return False


def resolve_transcripts_root(
    transcripts_dir: str | Path | None = None,
) -> Path:
    root = Path(transcripts_dir) if transcripts_dir is not None else Path(
        DIARISED_TRANSCRIPTS_DIR
    )
    return root.expanduser().resolve(strict=False)


def is_verified_app_imports_file(path: Path) -> bool:
    """True when path is a regular file under the managed transcripts/imports/ tree."""
    try:
        transcripts_root = Path(DIARISED_TRANSCRIPTS_DIR).expanduser().resolve(
            strict=False
        )
        imports_root = (transcripts_root / "imports").resolve(strict=False)
        # Also accept the configured imports alias when it differs.
        configured = Path(TRANSCRIPTS_IMPORTS_DIR).expanduser().resolve(strict=False)
        candidate = path.expanduser().resolve(strict=False)
    except OSError:
        return False
    under_imports = is_under_directory(candidate, imports_root) or is_under_directory(
        candidate, configured
    )
    if not under_imports or candidate in {imports_root, configured}:
        return False
    try:
        st = os.lstat(candidate)
    except OSError:
        return False
    return stat.S_ISREG(st.st_mode)
