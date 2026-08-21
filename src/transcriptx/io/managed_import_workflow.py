"""Public managed-import workflow entry and result types."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from transcriptx.core.utils.file_lock import FileLock
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import (
    DIARISED_TRANSCRIPTS_DIR,
    TRANSCRIPTS_ORIGINALS_DIR,
)
from transcriptx.io.atomic_json import write_json_atomic
from transcriptx.io.import_admission import (
    AdmissionError,
    ManagedArtifactState,
    assert_within_import_size_limit,
    derive_canonical_target,
    inspect_managed_artifact_state,
    is_verified_app_imports_file,
    sanitize_upload_basename,
    validate_safe_originals_relpath,
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
from transcriptx.io.originals_archive import exclusive_create_originals_archive
from transcriptx.io.speaker_map_inheritance import apply_speaker_map_on_import
from transcriptx.io.transcript_importer import import_transcript

logger = get_logger()


class StagingCleanupPolicy(str, Enum):
    """Ownership-aware cleanup for app-created staging/snapshot files."""

    NEVER = "never"
    APP_IMPORTS_ONLY = "app_imports_only"


@dataclass(frozen=True)
class ManagedImportResult:
    import_id: str
    imported_at: str
    json_path: Path
    archived_original_path: Path
    archived_original_relpath: str
    adapter_source_id: str
    sidecar_path: Path
    repaired_incomplete: bool = False
    speaker_map_error: str | None = None


@dataclass
class _AttemptCreated:
    """Paths created by the current attempt (rollback scope)."""

    archive: Path | None = None
    json_path: Path | None = None
    sidecar: Path | None = None
    extra: list[Path] = field(default_factory=list)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_object_from_document(doc: dict[str, Any]) -> dict[str, Any]:
    raw = doc.get("source")
    return raw if isinstance(raw, dict) else {}


def _cleanup_app_owned_staging(
    staging_path: Path,
    *,
    policy: StagingCleanupPolicy,
    skip_unlink_if_same_as: Path | None = None,
) -> None:
    if policy is StagingCleanupPolicy.NEVER:
        return
    if not is_verified_app_imports_file(staging_path):
        logger.warning(
            "Refusing staging cleanup for non-app-owned path: %s", staging_path
        )
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


def _rollback_attempt(created: _AttemptCreated) -> None:
    for path in (created.sidecar, created.json_path, created.archive, *created.extra):
        if path is None:
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Rollback could not remove %s: %s", path, exc)


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
    with open(json_path, "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    source = _source_object_from_document(doc) if isinstance(doc, dict) else {}
    rel = str(source.get("original_path") or "")
    normalized, _archive = validate_safe_originals_relpath(rel, output_dir=output_dir)
    return normalized


def _backfill_retry_original_path_from_app_staging(
    *,
    json_path: Path,
    staging_path: Path,
    output_dir: Path,
    originals_dir: Path,
    imported_at: str,
    archive_basename: str,
    created: _AttemptCreated,
) -> str:
    """Backfill missing provenance using verified app-owned staging only.

    Uses atomic JSON replacement. Does not pair arbitrary folder sources.
    """
    if not is_verified_app_imports_file(staging_path):
        raise AdmissionError(
            "Cannot backfill provenance from a non-app-owned source file."
        )
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

    content = staging_path.read_bytes()
    assert_within_import_size_limit(len(content))
    archive_dest = exclusive_create_originals_archive(
        archive_basename,
        originals_dir,
        content,
        staging_path=staging_path,
    )
    created.archive = archive_dest
    archived_relpath = str(archive_dest.relative_to(output_dir))

    source["original_path"] = archived_relpath
    if not source.get("imported_at"):
        source["imported_at"] = imported_at
    if not source.get("type"):
        source["type"] = "manual"
    doc["source"] = source
    write_json_atomic(json_path, doc, indent=2)
    return archived_relpath


def _apply_speaker_map_recoverable(json_path: Path) -> str | None:
    try:
        apply_speaker_map_on_import(json_path)
    except Exception as exc:
        logger.warning(
            "Speaker map inheritance failed after artifact commit for %s: %s",
            json_path,
            exc,
        )
        return str(exc)
    return None


def run_managed_import_workflow(
    staging_path: str | Path,
    *,
    logical_upload_basename: str | None = None,
    overwrite: bool = False,
    delete_staging_on_success: bool | None = None,
    staging_cleanup: StagingCleanupPolicy | None = None,
    allow_provenance_backfill: bool = True,
    acquire_lock: bool = True,
) -> ManagedImportResult:
    """Import transcript into managed artifact set (archive + canonical + sidecar).

    ``logical_upload_basename`` is the client-visible filename (e.g. Streamlit upload
    name). When staging lives under ``imports/`` with a UUID-prefixed name, pass the
    original basename so canonical JSON is ``<stem>.json`` and ``originals/`` uses the
    same basename (with numeric disambiguation only for real collisions).

    ``delete_staging_on_success`` is retained for callers; when True it maps to
    :attr:`StagingCleanupPolicy.APP_IMPORTS_ONLY` (never deletes non-imports paths).
    Prefer ``staging_cleanup`` for new code.

    When ``acquire_lock`` is False, the caller must already hold the per-target
    :class:`FileLock` for the derived JSON path.
    """
    staging = Path(staging_path)
    if not staging.exists():
        raise FileNotFoundError(f"Staging file not found: {staging}")

    if staging_cleanup is None:
        if delete_staging_on_success:
            staging_cleanup = StagingCleanupPolicy.APP_IMPORTS_ONLY
        else:
            staging_cleanup = StagingCleanupPolicy.NEVER

    import_id = str(uuid.uuid4())
    imported_at = _utc_now_iso()
    output_dir = Path(DIARISED_TRANSCRIPTS_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    originals_dir = Path(TRANSCRIPTS_ORIGINALS_DIR)

    raw_basename = (
        logical_upload_basename if logical_upload_basename is not None else staging.name
    )
    # Prefer shared admission sanitisation; fall back to Path.name for rare
    # adapter extensions outside the GUI frozenset (legacy API callers).
    try:
        archive_basename = sanitize_upload_basename(raw_basename)
        target = derive_canonical_target(archive_basename, transcripts_dir=output_dir)
        target_json = target.target_json
        canonical_stem = target.display_stem
    except AdmissionError:
        archive_basename = (
            Path(str(raw_basename).replace("\\", "/")).name or staging.name
        )
        if not archive_basename or archive_basename in {".", ".."}:
            raise
        canonical_stem = Path(archive_basename).stem
        if not canonical_stem:
            raise AdmissionError("Upload filename has an empty stem.")
        target_json = output_dir / f"{canonical_stem}.json"

    def _run_locked() -> ManagedImportResult:
        return _run_managed_import_body(
            staging=staging,
            archive_basename=archive_basename,
            canonical_stem=canonical_stem,
            target_json=target_json,
            output_dir=output_dir,
            originals_dir=originals_dir,
            import_id=import_id,
            imported_at=imported_at,
            overwrite=overwrite,
            staging_cleanup=staging_cleanup,
            allow_provenance_backfill=allow_provenance_backfill,
        )

    if not acquire_lock:
        return _run_locked()

    with FileLock(target_json, timeout=30) as lock:
        if not lock.acquired:
            raise RuntimeError(f"Could not acquire import lock for {target_json}")
        return _run_locked()


def _run_managed_import_body(
    *,
    staging: Path,
    archive_basename: str,
    canonical_stem: str,
    target_json: Path,
    output_dir: Path,
    originals_dir: Path,
    import_id: str,
    imported_at: str,
    overwrite: bool,
    staging_cleanup: StagingCleanupPolicy,
    allow_provenance_backfill: bool,
) -> ManagedImportResult:
    derived_sidecar = sidecar_path_for_transcript(target_json)
    created = _AttemptCreated()
    inspection = inspect_managed_artifact_state(
        target_json,
        sidecar_path=derived_sidecar,
        transcripts_dir=output_dir,
    )

    # Retry / repair boundary when JSON exists and overwrite is false.
    # Schema-invalid occupants (e.g. raw WhisperX dropped into the library root)
    # fall through to full admission with replace, instead of trying to patch the
    # invalid document in place (which can fail on vendor NaNs/Infs).
    replace_schema_invalid = False
    if target_json.exists() and not overwrite:
        if inspection.state is ManagedArtifactState.ALREADY_MANAGED:
            raise FileExistsError(
                f"Transcript already exists and sidecar exists: {target_json}"
            )
        if inspection.state is ManagedArtifactState.INCONSISTENT:
            raise ValueError(inspection.detail or "Inconsistent managed sidecar state")
        if inspection.state is ManagedArtifactState.INCOMPLETE_REPAIRABLE:
            rel = inspection.archived_original_relpath
            assert rel is not None
        elif inspection.state is ManagedArtifactState.INCOMPLETE_UNREPAIRABLE:
            # Only missing provenance may be backfilled from app-owned staging.
            # Unsafe/present original_path must surface as a hard error (no pairing).
            # Marker-less JSON (no schema_version — e.g. raw WhisperX) is replaced
            # via new admission below so vendor NaNs cannot block atomic writes.
            try:
                with open(target_json, "r", encoding="utf-8") as handle:
                    doc = json.load(handle)
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(
                    inspection.detail or "Incomplete managed transcript is not readable"
                ) from exc
            has_schema_marker = isinstance(doc, dict) and "schema_version" in doc
            if not has_schema_marker:
                logger.info(
                    "Replacing marker-less library JSON via managed admission: %s",
                    target_json,
                )
                replace_schema_invalid = True
            else:
                source = _source_object_from_document(doc)
                existing_rel = str(source.get("original_path") or "").strip()
                if existing_rel:
                    # Re-raise the precise safety error (e.g. must be under originals/).
                    validate_safe_originals_relpath(existing_rel, output_dir=output_dir)
                    raise ValueError(
                        inspection.detail
                        or "Incomplete managed transcript is not repairable"
                    )
                if not allow_provenance_backfill:
                    raise ValueError(
                        inspection.detail
                        or "Incomplete managed transcript is not repairable"
                    )
                try:
                    rel = _backfill_retry_original_path_from_app_staging(
                        json_path=target_json,
                        staging_path=staging,
                        output_dir=output_dir,
                        originals_dir=originals_dir,
                        imported_at=imported_at,
                        archive_basename=archive_basename,
                        created=created,
                    )
                except Exception:
                    _rollback_attempt(created)
                    raise
        else:
            raise ValueError(f"Unexpected managed state for retry: {inspection.state}")

        if not replace_schema_invalid:
            try:
                sidecar_retry_path = _write_sidecar_for_existing_json(
                    json_path=target_json,
                    import_id=import_id,
                    imported_at=imported_at,
                    source_upload_basename=archive_basename,
                    archived_original_relpath=rel,
                )
                created.sidecar = sidecar_retry_path
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
                        "Managed transcript validation failed after sidecar retry: "
                        f"{validation.message}"
                    )
            except Exception:
                _rollback_attempt(created)
                raise

            _cleanup_app_owned_staging(
                staging,
                policy=staging_cleanup,
                skip_unlink_if_same_as=output_dir / rel,
            )
            with open(target_json, "r", encoding="utf-8") as handle:
                doc = json.load(handle)
            source = doc.get("source", {}) if isinstance(doc, dict) else {}
            source_type = str(source.get("type") or "existing")
            archived_path = output_dir / rel
            speaker_err = _apply_speaker_map_recoverable(target_json)
            return ManagedImportResult(
                import_id=import_id,
                imported_at=imported_at,
                json_path=target_json,
                archived_original_path=archived_path,
                archived_original_relpath=rel,
                adapter_source_id=source_type,
                sidecar_path=sidecar_retry_path,
                repaired_incomplete=True,
                speaker_map_error=speaker_err,
            )

    # New admission: parse snapshot first, then exclusive-create archive, then write.
    try:
        content = staging.read_bytes()
        assert_within_import_size_limit(len(content))

        registry = build_default_registry()
        # Provisional orchestration uses staging as source path; final original_path
        # is set to the exclusive archive relpath after create.
        # We exclusive-create first with the same bytes so document provenance is final.
        archive_dest = exclusive_create_originals_archive(
            archive_basename,
            originals_dir,
            content,
            staging_path=staging,
        )
        created.archive = archive_dest
        archived_relpath = str(archive_dest.relative_to(output_dir))

        import_result = run_import_orchestration(
            source_path=staging,
            registry=registry,
            imported_at=imported_at,
            source_original_path=archived_relpath,
            normalization_policy=NormalizationPolicy(),
        )
        writer = AtomicTranscriptWriter(reason="import")
        json_path = writer.write(
            target_json,
            import_result.canonical_document,
            overwrite=overwrite or replace_schema_invalid,
        )
        created.json_path = json_path

        sidecar_path = write_initial_sidecar(
            json_path,
            import_id=import_id,
            imported_at=imported_at,
            adapter_source_id=import_result.selected_adapter_id,
            source_upload_basename=archive_basename,
            archived_original_relpath=archived_relpath,
        )
        created.sidecar = sidecar_path

        validation = validate_managed_transcript(json_path)
        if not validation.ok:
            raise ValueError(
                f"Managed transcript validation failed after import: {validation.message}"
            )
    except Exception:
        _rollback_attempt(created)
        raise

    _cleanup_app_owned_staging(
        staging,
        policy=staging_cleanup,
        skip_unlink_if_same_as=archive_dest,
    )
    speaker_err = _apply_speaker_map_recoverable(json_path)
    return ManagedImportResult(
        import_id=import_id,
        imported_at=imported_at,
        json_path=json_path,
        archived_original_path=archive_dest,
        archived_original_relpath=archived_relpath,
        adapter_source_id=import_result.selected_adapter_id,
        sidecar_path=sidecar_path,
        repaired_incomplete=replace_schema_invalid,
        speaker_map_error=speaker_err,
    )
