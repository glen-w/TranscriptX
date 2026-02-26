"""
Database maintenance utilities (one-off / admin style operations).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import delete, func, or_
from sqlalchemy.orm import Session

from transcriptx.core.utils.paths import OUTPUTS_DIR  # type: ignore[import-untyped]
from transcriptx.database.models import (  # type: ignore[import-untyped]
    ArtifactIndex,
    ModuleRun,
    PipelineRun,
    TranscriptFile,
)


@dataclass(frozen=True)
class PrunedRunInfo:
    id: int
    created_at: Optional[datetime]
    status: str


@dataclass(frozen=True)
class PrunePlanItem:
    transcript_file_id: int
    transcript_file_name: Optional[str]
    keep: PrunedRunInfo
    delete: List[PrunedRunInfo]


@dataclass
class PruneOldRunsReport:
    dry_run: bool
    transcripts_considered: int = 0
    transcripts_with_deletions: int = 0
    pipeline_runs_to_delete: int = 0
    pipeline_runs_deleted: int = 0
    plan: List[PrunePlanItem] = field(default_factory=list)

    # File deletion (optional)
    artifact_candidates: int = 0
    files_deleted: int = 0
    files_skipped: int = 0
    files_missing: int = 0
    files_unsafe_outside_outputs: int = 0

    # Disk-only runs (runs on disk but not in DB)
    disk_only_slugs_scanned: int = 0
    disk_only_runs_found: int = 0
    disk_only_runs_to_delete: int = 0
    disk_only_runs_deleted: int = 0
    disk_only_plan: List[tuple[str, List[str], str]] = field(
        default_factory=list
    )  # (slug, runs_to_delete, keep_run)


def _choose_keep_run(runs: List[PipelineRun]) -> PipelineRun:
    return sorted(
        runs,
        key=lambda r: (r.created_at or datetime.min, r.id),
        reverse=True,
    )[0]


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _gather_artifact_candidates_for_deleted_pipeline_runs(
    session: Session, pipeline_run_ids_to_delete: Sequence[int]
) -> tuple[Set[int], Dict[Tuple[str, str], Path]]:
    """
    Returns:
      - module_run_ids_to_delete
      - unique artifact paths keyed by (artifact_root, relative_path)
    """
    if not pipeline_run_ids_to_delete:
        return set(), {}

    module_run_ids = {
        row[0]
        for row in session.query(ModuleRun.id)
        .filter(ModuleRun.pipeline_run_id.in_(list(pipeline_run_ids_to_delete)))
        .all()
    }
    if not module_run_ids:
        return set(), {}

    artifact_rows: List[ArtifactIndex] = (
        session.query(ArtifactIndex)
        .filter(
            ArtifactIndex.module_run_id.in_(list(module_run_ids)),
            ArtifactIndex.artifact_root.isnot(None),
        )
        .all()
    )
    candidates: Dict[Tuple[str, str], Path] = {}
    for row in artifact_rows:
        if not row.artifact_root:
            continue
        key = (row.artifact_root, row.relative_path)
        candidates[key] = (Path(row.artifact_root) / row.relative_path).resolve()
    return module_run_ids, candidates


def _artifact_is_still_referenced(
    session: Session,
    *,
    artifact_root: str,
    relative_path: str,
    excluding_module_run_ids: Set[int],
) -> bool:
    q = session.query(func.count(ArtifactIndex.id)).filter(
        ArtifactIndex.artifact_root == artifact_root,
        ArtifactIndex.relative_path == relative_path,
    )
    if excluding_module_run_ids:
        # Preserve NULL module_run_id references (e.g. sidecar artifacts).
        q = q.filter(
            or_(
                ArtifactIndex.module_run_id.is_(None),
                ArtifactIndex.module_run_id.notin_(excluding_module_run_ids),
            )
        )
    return (q.scalar() or 0) > 0


def prune_old_pipeline_runs(
    session: Session,
    *,
    transcript_file_ids: Optional[Sequence[int]] = None,
    file_name_contains: Optional[str] = None,
    limit: Optional[int] = None,
    apply: bool = False,
    delete_files: bool = False,
    outputs_root: Optional[Path] = None,
) -> PruneOldRunsReport:
    """
    Keep the most recent PipelineRun (by created_at) per transcript_file_id and
    delete the rest.

    Important: Deletes use SQL DELETE so DB ON DELETE CASCADE removes dependent
    module_runs and artifact_index records.
    """
    outputs_root = (outputs_root or Path(OUTPUTS_DIR)).resolve()
    report = PruneOldRunsReport(dry_run=not apply)

    # Find transcript_file_id values that have > 1 PipelineRun.
    q = (
        session.query(TranscriptFile.id)
        .join(PipelineRun, PipelineRun.transcript_file_id == TranscriptFile.id)
        .group_by(TranscriptFile.id)
        .having(func.count(PipelineRun.id) > 1)
        .order_by(TranscriptFile.id.asc())
    )
    if transcript_file_ids:
        q = q.filter(TranscriptFile.id.in_(list(transcript_file_ids)))
    if file_name_contains:
        q = q.filter(TranscriptFile.file_name.contains(file_name_contains))
    if limit is not None:
        q = q.limit(limit)

    transcript_ids = [row[0] for row in q.all()]
    report.transcripts_considered = len(transcript_ids)

    run_ids_to_delete: List[int] = []

    for transcript_file_id in transcript_ids:
        runs: List[PipelineRun] = (
            session.query(PipelineRun)
            .filter(PipelineRun.transcript_file_id == transcript_file_id)
            .order_by(PipelineRun.created_at.desc(), PipelineRun.id.desc())
            .all()
        )
        if len(runs) <= 1:
            continue

        keep = _choose_keep_run(runs)
        delete_runs = [r for r in runs if r.id != keep.id]
        if not delete_runs:
            continue

        tf: Optional[TranscriptFile] = (
            session.query(TranscriptFile)
            .filter(TranscriptFile.id == transcript_file_id)
            .first()
        )

        report.transcripts_with_deletions += 1
        report.pipeline_runs_to_delete += len(delete_runs)

        report.plan.append(
            PrunePlanItem(
                transcript_file_id=transcript_file_id,
                transcript_file_name=tf.file_name if tf else None,
                keep=PrunedRunInfo(
                    id=keep.id,
                    created_at=getattr(keep, "created_at", None),
                    status=getattr(keep, "status", "unknown"),
                ),
                delete=[
                    PrunedRunInfo(
                        id=r.id,
                        created_at=getattr(r, "created_at", None),
                        status=getattr(r, "status", "unknown"),
                    )
                    for r in delete_runs
                ],
            )
        )
        if apply:
            run_ids_to_delete.extend([r.id for r in delete_runs])

    # Prune disk-only runs (runs on disk but not in DB)
    # This runs in both dry-run and apply modes
    _prune_disk_only_runs(
        session,
        report,
        outputs_root,
        transcript_file_ids=transcript_file_ids,
        apply=apply,
    )

    if not apply:
        return report

    # Optional: gather artifact file candidates before deleting (for later FS cleanup).
    module_run_ids_to_delete: Set[int] = set()
    artifact_paths: Dict[Tuple[str, str], Path] = {}
    if delete_files and run_ids_to_delete:
        module_run_ids_to_delete, artifact_paths = (
            _gather_artifact_candidates_for_deleted_pipeline_runs(
                session, run_ids_to_delete
            )
        )
        report.artifact_candidates = len(artifact_paths)

    if run_ids_to_delete:
        session.execute(
            delete(PipelineRun).where(PipelineRun.id.in_(run_ids_to_delete))
        )
    session.commit()
    report.pipeline_runs_deleted = len(run_ids_to_delete)

    if not delete_files or not artifact_paths:
        return report

    # Delete unreferenced files under outputs_root only.
    for (artifact_root, relative_path), abs_path in artifact_paths.items():
        if not _is_relative_to(abs_path, outputs_root):
            report.files_unsafe_outside_outputs += 1
            continue
        if _artifact_is_still_referenced(
            session,
            artifact_root=artifact_root,
            relative_path=relative_path,
            excluding_module_run_ids=module_run_ids_to_delete,
        ):
            report.files_skipped += 1
            continue
        if not abs_path.exists():
            report.files_missing += 1
            continue
        try:
            abs_path.unlink()
            report.files_deleted += 1
        except Exception:
            report.files_skipped += 1

    return report


def _is_valid_run_id(run_id: str) -> bool:
    """
    Check if a string is a valid run_id format.

    Run ID format: YYYYMMDD_HHMMSS_hex8 (24 characters total)
    """
    if len(run_id) != 24:
        return False
    if run_id[8] != "_" or run_id[15] != "_":
        return False
    try:
        date_part = run_id[:8]  # YYYYMMDD
        time_part = run_id[9:15]  # HHMMSS
        hex_part = run_id[16:]  # hex8
        int(date_part)  # Validate it's numeric
        int(time_part)  # Validate it's numeric
        int(hex_part, 16)  # Validate it's hex
        return True
    except (ValueError, IndexError):
        return False


def _extract_run_id_from_path(path: Path) -> Optional[str]:
    """
    Extract run_id from a path like outputs/<slug>/<run_id>/...

    Returns the run_id if the path matches the expected structure, None otherwise.
    Run ID format: YYYYMMDD_HHMMSS_hex8 (24 characters total)
    """
    try:
        parts = path.parts
        # Look for pattern: .../outputs/<slug>/<run_id>/...
        # Run IDs are in format: YYYYMMDD_HHMMSS_hex8 (8+1+6+1+8 = 24 chars)
        for part in parts:
            if _is_valid_run_id(part):
                return part
    except Exception:
        pass
    return None


def _get_db_run_ids_for_slug(
    session: Session, slug: str, outputs_root: Path
) -> Set[str]:
    """
    Get all run_ids that are referenced in the database for a given slug.

    This checks artifact_root paths in ArtifactIndex to find which run_ids
    are tracked in the database.
    """
    run_ids: Set[str] = set()
    slug_path = outputs_root / slug

    # Query all artifact_root paths that contain this slug
    artifact_rows = (
        session.query(ArtifactIndex.artifact_root)
        .filter(ArtifactIndex.artifact_root.isnot(None))
        .all()
    )

    for row in artifact_rows:
        if not row.artifact_root:
            continue
        artifact_path = Path(row.artifact_root)
        # Check if this artifact is under the slug directory
        try:
            artifact_path.relative_to(slug_path)
            # Extract run_id from the path
            run_id = _extract_run_id_from_path(artifact_path)
            if run_id:
                run_ids.add(run_id)
        except ValueError:
            # Path is not under this slug directory
            continue

    return run_ids


def _find_disk_only_runs(
    session: Session,
    outputs_root: Path,
    transcript_file_ids: Optional[Sequence[int]] = None,
) -> Dict[str, List[str]]:
    """
    Find run directories on disk that are not tracked in the database.

    Note: When transcript_file_ids is provided, we still scan all slugs since
    disk-only runs aren't in the DB and can't be filtered by transcript_file_id.

    Returns:
        Dictionary mapping slug to list of run_ids that exist on disk but not in DB
    """
    disk_only_runs: Dict[str, List[str]] = {}

    if not outputs_root.exists():
        return disk_only_runs

    # Scan all slug directories
    # Note: We scan all slugs regardless of transcript_file_ids filter because
    # disk-only runs aren't in the DB and can't be matched to transcript_file_ids
    for slug_dir in outputs_root.iterdir():
        if not slug_dir.is_dir() or slug_dir.name.startswith("."):
            continue

        slug = slug_dir.name

        # Get all run directories for this slug
        run_dirs = [
            p for p in slug_dir.iterdir() if p.is_dir() and not p.name.startswith(".")
        ]
        if len(run_dirs) <= 1:
            continue

        # Get run_ids tracked in DB for this slug
        db_run_ids = _get_db_run_ids_for_slug(session, slug, outputs_root)

        # Find run_ids on disk that aren't in DB
        disk_run_ids = []
        for run_dir in run_dirs:
            run_id = run_dir.name
            # Validate it looks like a run_id (format: YYYYMMDD_HHMMSS_hex8)
            if _is_valid_run_id(run_id) and run_id not in db_run_ids:
                disk_run_ids.append(run_id)

        if disk_run_ids:
            disk_only_runs[slug] = sorted(disk_run_ids)

    return disk_only_runs


def _prune_disk_only_runs(
    session: Session,
    report: PruneOldRunsReport,
    outputs_root: Path,
    transcript_file_ids: Optional[Sequence[int]] = None,
    apply: bool = False,
) -> None:
    """
    Prune disk-only runs (runs that exist on disk but not in the database).

    For each slug with multiple disk-only runs, keeps the most recent (by run_id timestamp)
    and marks the rest for deletion.
    """
    disk_only_runs = _find_disk_only_runs(session, outputs_root, transcript_file_ids)
    report.disk_only_slugs_scanned = len(disk_only_runs)

    for slug, run_ids in disk_only_runs.items():
        report.disk_only_runs_found += len(run_ids)

        if len(run_ids) <= 1:
            continue

        # Sort by run_id (which contains timestamp, so most recent is last)
        sorted_runs = sorted(run_ids)
        keep_run = sorted_runs[-1]  # Keep the most recent
        delete_runs = sorted_runs[:-1]  # Delete all others

        report.disk_only_runs_to_delete += len(delete_runs)
        report.disk_only_plan.append((slug, delete_runs, keep_run))

        if apply:
            slug_dir = outputs_root / slug
            for run_id in delete_runs:
                run_dir = slug_dir / run_id
                if run_dir.exists() and _is_relative_to(run_dir, outputs_root):
                    try:
                        import shutil

                        shutil.rmtree(run_dir)
                        report.disk_only_runs_deleted += 1
                    except Exception:
                        pass
