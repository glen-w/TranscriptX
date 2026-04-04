from __future__ import annotations

import json
import posixpath
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from transcriptx.core.utils.file_lock import FileLock
from transcriptx.core.utils.paths import (
    DIARISED_TRANSCRIPTS_DIR,
    TRANSCRIPTS_ORIGINALS_DIR,
)
from transcriptx.io.import_adapters.registry_builtins import build_default_registry
from transcriptx.io.import_core.normalization_policy import NormalizationPolicy
from transcriptx.io.import_core.orchestrator import run_import_orchestration
from transcriptx.io.import_core.writer import AtomicTranscriptWriter
from transcriptx.io.import_managed.sidecar import (
    sidecar_path_for_transcript,
    validate_managed_transcript,
    write_initial_sidecar,
)
from transcriptx.io.originals_archive import disambiguate_originals_archive_path


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
    staging_path.unlink(missing_ok=True)


def _extract_retry_source_original_relpath(*, json_path: Path, output_dir: Path) -> str:
    with open(json_path, "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    source = doc.get("source", {}) if isinstance(doc, dict) else {}
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


def run_managed_import_workflow(
    staging_path: str | Path,
    *,
    logical_upload_basename: str | None = None,
    overwrite: bool = False,
    delete_staging_on_success: bool = False,
) -> ManagedImportResult:
    staging = Path(staging_path)
    if not staging.exists():
        raise FileNotFoundError(f"Staging file not found: {staging}")

    import_id = str(uuid.uuid4())
    imported_at = _utc_now_iso()
    output_dir = Path(DIARISED_TRANSCRIPTS_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_basename = (
        Path(logical_upload_basename).name
        if logical_upload_basename
        else staging.name
    )
    canonical_stem = Path(archive_basename).stem
    target_json = output_dir / f"{canonical_stem}.json"
    originals_dir = Path(TRANSCRIPTS_ORIGINALS_DIR)

    with FileLock(target_json, timeout=30) as lock:
        if not lock.acquired:
            raise RuntimeError(f"Could not acquire import lock for {target_json}")
        derived_sidecar = sidecar_path_for_transcript(target_json)
        if target_json.exists() and not overwrite:
            if derived_sidecar.exists():
                raise FileExistsError(
                    f"Transcript already exists and sidecar exists: {target_json}"
                )
            rel = _extract_retry_source_original_relpath(
                json_path=target_json, output_dir=output_dir
            )
            sidecar_retry_path = write_initial_sidecar(
                target_json,
                import_id=import_id,
                imported_at=imported_at,
                adapter_source_id="existing",
                source_upload_basename=archive_basename,
                archived_original_relpath=rel,
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
            return ManagedImportResult(
                import_id=import_id,
                imported_at=imported_at,
                json_path=target_json,
                archived_original_path=output_dir / rel,
                archived_original_relpath=rel,
                adapter_source_id="existing",
                sidecar_path=sidecar_retry_path,
            )

        archive_dest = disambiguate_originals_archive_path(
            archive_basename, originals_dir, staging_path=staging
        )
        archive_dest.write_bytes(staging.read_bytes())
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
        return ManagedImportResult(
            import_id=import_id,
            imported_at=imported_at,
            json_path=json_path,
            archived_original_path=archive_dest,
            archived_original_relpath=archived_relpath,
            adapter_source_id=import_result.selected_adapter_id,
            sidecar_path=sidecar_path,
        )
