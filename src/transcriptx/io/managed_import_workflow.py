from __future__ import annotations

import json
import posixpath
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from transcriptx.core.utils.file_lock import FileLock
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import (
    DIARISED_TRANSCRIPTS_DIR,
    TRANSCRIPTS_ORIGINALS_DIR,
)
from transcriptx.io.import_adapters.registry_builtins import build_default_registry
from transcriptx.io.import_core.normalization_policy import NormalizationPolicy
from transcriptx.io.import_core.orchestrator import run_import_orchestration
from transcriptx.io.import_core.writer import AtomicTranscriptWriter
from transcriptx.io.import_metadata_sidecar import (
    sidecar_path_for_transcript,
    validate_managed_transcript,
    write_initial_sidecar,
)
from transcriptx.io.originals_archive import disambiguate_originals_archive_path
from transcriptx.io.speaker_map_inheritance import apply_speaker_map_on_import
from transcriptx.io.transcript_importer import import_transcript

logger = get_logger()


@dataclass(frozen=True)
class ManagedImportResult:
    import_id: str
    imported_at: str
    json_path: Path
    archived_original_path: Path
    archived_original_relpath: str
    adapter_source_id: str
    sidecar_path: Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_object_from_document(doc: dict[str, Any]) -> dict[str, Any]:
    """Return ``doc['source']`` when it is a JSON object; otherwise ``{}``."""
    raw = doc.get("source")
    return raw if isinstance(raw, dict) else {}


def _cleanup_staging_file_if_requested(
    staging_path: Path,
    *,
    delete_staging: bool,
    skip_unlink_if_same_as: Path | None = None,
) -> None:
    if not delete_staging:
        return
    if skip_unlink_if_same_as is not None:
        try:
            if staging_path.resolve() == skip_unlink_if_same_as.resolve():
                return
        except OSError:
            pass
    try:
        staging_path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Could not delete staging file %s: %s", staging_path, exc)


def _write_sidecar_for_existing_json(
    *,
    json_path: Path,
    import_id: str,
    imported_at: str,
    source_upload_basename: str,
    archived_original_relpath: str | None = None,
) -> Path:
    with open(json_path, "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    source = _source_object_from_document(doc) if isinstance(doc, dict) else {}
    adapter_source_id = str(source.get("type") or "existing")
    original_relpath = archived_original_relpath or str(
        source.get("original_path") or ""
    )
    if not original_relpath:
        raise ValueError("Existing JSON has no source.original_path for sidecar retry")
    return write_initial_sidecar(
        json_path,
        import_id=import_id,
        imported_at=imported_at,
        adapter_source_id=adapter_source_id,
        source_upload_basename=source_upload_basename,
        archived_original_relpath=original_relpath,
    )


def _extract_retry_source_original_relpath(
    *,
    json_path: Path,
    output_dir: Path,
) -> str:
    """Return validated source.original_path from an existing canonical JSON.

    Retry is allowed only when the existing JSON is already schema-valid and its
    source.original_path points to a normalized relative path under originals/.
    """
    with open(json_path, "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    source = _source_object_from_document(doc) if isinstance(doc, dict) else {}
    rel = str(source.get("original_path") or "")
    if not rel:
        raise ValueError("Existing JSON has no source.original_path for sidecar retry")
    normalized = posixpath.normpath(rel.replace("\\", "/"))
    if normalized in {".", ".."} or normalized.startswith("../"):
        raise ValueError(
            "Existing JSON source.original_path is not a safe relative path"
        )
    if not normalized.startswith("originals/"):
        raise ValueError("Existing JSON source.original_path must be under originals/")
    archive_path = output_dir / normalized
    if not archive_path.exists():
        raise ValueError("Existing JSON source.original_path target is missing on disk")
    return normalized


def _backfill_retry_original_path_from_staging(
    *,
    json_path: Path,
    staging_path: Path,
    output_dir: Path,
    originals_dir: Path,
    imported_at: str,
    archive_basename: str,
) -> str:
    """Backfill missing source.original_path for sidecar retry using staging upload."""
    with open(json_path, "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    if not isinstance(doc, dict):
        raise ValueError("Existing JSON root must be an object for sidecar retry")
    raw_source = doc.get("source")
    source = dict(raw_source) if isinstance(raw_source, dict) else {}
    if raw_source is not None and not isinstance(raw_source, dict):
        logger.warning(
            "Sidecar retry: replacing non-object source with a new object (was %s)",
            type(raw_source).__name__,
        )
    if source.get("original_path"):
        raise ValueError("source.original_path already present; backfill not required")

    archive_dest = disambiguate_originals_archive_path(
        archive_basename, originals_dir, staging_path=staging_path
    )
    archive_dest.write_bytes(staging_path.read_bytes())
    archived_relpath = str(archive_dest.relative_to(output_dir))

    source["original_path"] = archived_relpath
    if not source.get("imported_at"):
        source["imported_at"] = imported_at
    if not source.get("type"):
        source["type"] = "manual"
    doc["source"] = source
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, ensure_ascii=False, indent=2)
    return archived_relpath


def run_managed_import_workflow(
    staging_path: str | Path,
    *,
    logical_upload_basename: str | None = None,
    overwrite: bool = False,
    delete_staging_on_success: bool = False,
) -> ManagedImportResult:
    """Import transcript into managed artifact set (archive + canonical + sidecar).

    ``logical_upload_basename`` is the client-visible filename (e.g. Streamlit upload
    name). When staging lives under ``imports/`` with a UUID-prefixed name, pass the
    original basename so canonical JSON is ``<stem>.json`` and ``originals/`` uses the
    same basename (with numeric disambiguation only for real collisions).
    """
    staging = Path(staging_path)
    if not staging.exists():
        raise FileNotFoundError(f"Staging file not found: {staging}")

    import_id = str(uuid.uuid4())
    imported_at = _utc_now_iso()
    output_dir = Path(DIARISED_TRANSCRIPTS_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_basename = (
        Path(logical_upload_basename).name if logical_upload_basename else staging.name
    )
    canonical_stem = Path(archive_basename).stem
    target_json = output_dir / f"{canonical_stem}.json"
    originals_dir = Path(TRANSCRIPTS_ORIGINALS_DIR)

    with FileLock(target_json, timeout=30) as lock:
        if not lock.acquired:
            raise RuntimeError(f"Could not acquire import lock for {target_json}")

        derived_sidecar = sidecar_path_for_transcript(target_json)

        # Retry boundary: allow stage-3 completion only when json exists and sidecar missing.
        if target_json.exists() and not overwrite:
            if derived_sidecar.exists():
                raise FileExistsError(
                    f"Transcript already exists and sidecar exists: {target_json}"
                )
            try:
                rel = _extract_retry_source_original_relpath(
                    json_path=target_json,
                    output_dir=output_dir,
                )
            except ValueError as exc:
                if "no source.original_path" not in str(exc):
                    raise
                rel = _backfill_retry_original_path_from_staging(
                    json_path=target_json,
                    staging_path=staging,
                    output_dir=output_dir,
                    originals_dir=originals_dir,
                    imported_at=imported_at,
                    archive_basename=archive_basename,
                )
            sidecar_retry_path = _write_sidecar_for_existing_json(
                json_path=target_json,
                import_id=import_id,
                imported_at=imported_at,
                source_upload_basename=archive_basename,
                archived_original_relpath=rel,
            )
            validation = validate_managed_transcript(target_json)
            if not validation.ok and (output_dir / rel).exists():
                import_transcript(
                    output_dir / rel,
                    output_dir=output_dir,
                    overwrite=True,
                    imported_at=imported_at,
                    source_original_path=rel,
                    canonical_json_stem=canonical_stem,
                )
                validation = validate_managed_transcript(target_json)
            if not validation.ok:
                raise ValueError(
                    f"Managed transcript validation failed after sidecar retry: {validation.message}"
                )
            _cleanup_staging_file_if_requested(
                staging,
                delete_staging=delete_staging_on_success,
                skip_unlink_if_same_as=output_dir / rel,
            )
            with open(target_json, "r", encoding="utf-8") as handle:
                doc = json.load(handle)
            source = doc.get("source", {}) if isinstance(doc, dict) else {}
            source_type = str(source.get("type") or "existing")
            archived_path = output_dir / rel
            apply_speaker_map_on_import(target_json)
            return ManagedImportResult(
                import_id=import_id,
                imported_at=imported_at,
                json_path=target_json,
                archived_original_path=archived_path,
                archived_original_relpath=rel,
                adapter_source_id=source_type,
                sidecar_path=sidecar_retry_path,
            )

        archive_dest = disambiguate_originals_archive_path(
            archive_basename, originals_dir, staging_path=staging
        )
        content = staging.read_bytes()
        archive_dest.write_bytes(content)
        archived_relpath = str(archive_dest.relative_to(output_dir))

        registry = build_default_registry()
        import_result = run_import_orchestration(
            source_path=archive_dest,
            registry=registry,
            imported_at=imported_at,
            source_original_path=archived_relpath,
            normalization_policy=NormalizationPolicy(),
        )
        writer = AtomicTranscriptWriter(reason="import")
        json_path = writer.write(
            target_json, import_result.canonical_document, overwrite=overwrite
        )

        sidecar_path = write_initial_sidecar(
            json_path,
            import_id=import_id,
            imported_at=imported_at,
            adapter_source_id=import_result.selected_adapter_id,
            source_upload_basename=archive_basename,
            archived_original_relpath=archived_relpath,
        )

        validation = validate_managed_transcript(json_path)
        if not validation.ok:
            raise ValueError(
                f"Managed transcript validation failed after import: {validation.message}"
            )

        _cleanup_staging_file_if_requested(
            staging,
            delete_staging=delete_staging_on_success,
            skip_unlink_if_same_as=archive_dest,
        )
        apply_speaker_map_on_import(json_path)
        return ManagedImportResult(
            import_id=import_id,
            imported_at=imported_at,
            json_path=json_path,
            archived_original_path=archive_dest,
            archived_original_relpath=archived_relpath,
            adapter_source_id=import_result.selected_adapter_id,
            sidecar_path=sidecar_path,
        )
