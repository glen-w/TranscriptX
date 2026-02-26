#!/usr/bin/env python3
"""
One-off cleanup script: delete all but the most recent PipelineRun per transcript.

This operates on the database tables:
- transcript_files
- pipeline_runs (and cascades to module_runs, artifact_index)

By default this script runs in DRY-RUN mode and prints what would be deleted.
To actually delete, pass --apply --yes.

Optionally, it can delete artifact files on disk that are no longer referenced by
any remaining ArtifactIndex record (safe, reference-counted).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import delete, func
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from transcriptx.core.utils.paths import OUTPUTS_DIR
from transcriptx.database import get_session, init_database
from transcriptx.database.migrations import require_up_to_date_schema
from transcriptx.database.models import (
    ArtifactIndex,
    ModuleRun,
    PipelineRun,
    TranscriptFile,
)


@dataclass(frozen=True)
class ArtifactPath:
    artifact_root: str
    relative_path: str

    def absolute_path(self) -> Path:
        return (Path(self.artifact_root) / self.relative_path).resolve()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete all but the most recent PipelineRun per transcript_file_id.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete records (default is dry-run). Requires --yes.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt (required with --apply).",
    )
    parser.add_argument(
        "--delete-files",
        action="store_true",
        help=(
            "Also delete artifact files on disk that are no longer referenced by any "
            "remaining ArtifactIndex record."
        ),
    )
    parser.add_argument(
        "--transcript-file-id",
        type=int,
        action="append",
        default=[],
        help="Only process these transcript_file_id values (repeatable).",
    )
    parser.add_argument(
        "--file-name-contains",
        type=str,
        default=None,
        help="Only process transcript files whose file_name contains this substring.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of transcript files processed (for testing).",
    )
    return parser.parse_args(list(argv))


def _select_target_transcript_file_ids(
    session,
    *,
    only_ids: List[int],
    file_name_contains: Optional[str],
    limit: Optional[int],
) -> List[int]:
    """
    Returns transcript_file_id values that have > 1 PipelineRun.
    """
    q = (
        session.query(TranscriptFile.id)
        .join(PipelineRun, PipelineRun.transcript_file_id == TranscriptFile.id)
        .group_by(TranscriptFile.id)
        .having(func.count(PipelineRun.id) > 1)
        .order_by(TranscriptFile.id.asc())
    )
    if only_ids:
        q = q.filter(TranscriptFile.id.in_(only_ids))
    if file_name_contains:
        q = q.filter(TranscriptFile.file_name.contains(file_name_contains))
    if limit is not None:
        q = q.limit(limit)
    return [row[0] for row in q.all()]


def _choose_keep_run(runs: List[PipelineRun]) -> PipelineRun:
    # Most recent by created_at, then id for determinism.
    return sorted(
        runs,
        key=lambda r: (
            r.created_at
            or datetime.min,  # created_at should exist; fallback keeps things sortable
            r.id,
        ),
        reverse=True,
    )[0]


def _gather_artifacts_for_module_runs(
    session, module_run_ids: List[int]
) -> List[ArtifactPath]:
    if not module_run_ids:
        return []
    rows: List[ArtifactIndex] = (
        session.query(ArtifactIndex)
        .filter(
            ArtifactIndex.module_run_id.in_(module_run_ids),
            ArtifactIndex.artifact_root.isnot(None),
        )
        .all()
    )
    artifacts: List[ArtifactPath] = []
    for row in rows:
        if not row.artifact_root:
            continue
        artifacts.append(
            ArtifactPath(
                artifact_root=row.artifact_root, relative_path=row.relative_path
            )
        )
    return artifacts


def _artifact_is_still_referenced(
    session,
    artifact: ArtifactPath,
    *,
    excluding_module_run_ids: Set[int],
) -> bool:
    q = session.query(func.count(ArtifactIndex.id)).filter(
        ArtifactIndex.artifact_root == artifact.artifact_root,
        ArtifactIndex.relative_path == artifact.relative_path,
    )
    if excluding_module_run_ids:
        # Important: preserve NULL module_run_id references (e.g. sidecar artifacts).
        q = q.filter(
            or_(
                ArtifactIndex.module_run_id.is_(None),
                ArtifactIndex.module_run_id.notin_(excluding_module_run_ids),
            )
        )
    return (q.scalar() or 0) > 0


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)

    # Initialize DB + enforce schema.
    init_database()
    require_up_to_date_schema()
    session = get_session()

    outputs_root = Path(OUTPUTS_DIR).resolve()
    print(
        f"DB cleanup: keep newest PipelineRun per transcript. outputs_root={outputs_root}"
    )

    if args.apply and not args.yes:
        print("ERROR: --apply requires --yes (safety).")
        return 2

    try:
        transcript_ids = _select_target_transcript_file_ids(
            session,
            only_ids=args.transcript_file_id,
            file_name_contains=args.file_name_contains,
            limit=args.limit,
        )
        if not transcript_ids:
            print(
                "Nothing to do: no transcripts have more than one PipelineRun (with current filters)."
            )
            return 0

        total_runs_to_delete = 0
        total_transcripts = 0
        run_ids_to_delete: List[int] = []

        # If deleting files, collect (root,rel) candidates and only delete those not referenced elsewhere.
        artifact_candidates: List[ArtifactPath] = []
        delete_module_run_ids: Set[int] = set()

        for transcript_file_id in transcript_ids:
            runs: List[PipelineRun] = (
                session.query(PipelineRun)
                .options(joinedload(PipelineRun.transcript_file))
                .filter(PipelineRun.transcript_file_id == transcript_file_id)
                .order_by(PipelineRun.created_at.desc(), PipelineRun.id.desc())
                .all()
            )
            if len(runs) <= 1:
                continue

            keep = _choose_keep_run(runs)
            delete_runs = [r for r in runs if r.id != keep.id]
            transcript_file: Optional[TranscriptFile] = keep.transcript_file

            total_transcripts += 1
            total_runs_to_delete += len(delete_runs)

            label = f"transcript_file_id={transcript_file_id}" + (
                f" file_name={transcript_file.file_name}" if transcript_file else ""
            )
            print(f"\n{label}")
            print(
                f"  KEEP PipelineRun id={keep.id} created_at={getattr(keep, 'created_at', None)} status={keep.status}"
            )
            for r in delete_runs:
                print(
                    f"  DELETE PipelineRun id={r.id} created_at={getattr(r, 'created_at', None)} status={r.status}"
                )

            if args.delete_files:
                run_ids = [r.id for r in delete_runs]
                module_ids = [
                    row[0]
                    for row in session.query(ModuleRun.id)
                    .filter(ModuleRun.pipeline_run_id.in_(run_ids))
                    .all()
                ]
                delete_module_run_ids.update(module_ids)
                artifact_candidates.extend(
                    _gather_artifacts_for_module_runs(session, module_ids)
                )

            if args.apply:
                # NOTE:
                # Deleting PipelineRun via the ORM can attempt to NULL out ModuleRun.pipeline_run_id
                # (relationship has no delete cascade configured), which violates NOT NULL.
                # We use a SQL DELETE so the DB's ON DELETE CASCADE handles module_runs/artifacts.
                run_ids_to_delete.extend([r.id for r in delete_runs])

        if not args.apply:
            print("\n---")
            print(
                f"DRY-RUN summary: transcripts={total_transcripts}, pipeline_runs_to_delete={total_runs_to_delete}"
            )
            if args.delete_files:
                print(
                    f"DRY-RUN note: would also consider deleting up to {len(artifact_candidates)} artifact records' files (reference-counted)."
                )
            return 0

        # Apply DB deletions (SQL DELETE; relies on ON DELETE CASCADE for module_runs/artifacts).
        if run_ids_to_delete:
            session.execute(
                delete(PipelineRun).where(PipelineRun.id.in_(run_ids_to_delete))
            )
        session.commit()
        print("\n---")
        print(
            f"DB delete committed: transcripts={total_transcripts}, pipeline_runs_deleted={total_runs_to_delete}"
        )

        # Optional: delete artifact files on disk (only if unreferenced).
        if args.delete_files and artifact_candidates:
            deleted_files = 0
            skipped_files = 0
            missing_files = 0
            unsafe_files = 0

            # De-duplicate paths to avoid redundant checks/deletes.
            unique_candidates: Dict[Tuple[str, str], ArtifactPath] = {
                (a.artifact_root, a.relative_path): a for a in artifact_candidates
            }

            for artifact in unique_candidates.values():
                abs_path = artifact.absolute_path()
                if not _is_relative_to(abs_path, outputs_root):
                    # Safety: never delete outside data/outputs.
                    unsafe_files += 1
                    continue
                if _artifact_is_still_referenced(
                    session, artifact, excluding_module_run_ids=delete_module_run_ids
                ):
                    skipped_files += 1
                    continue
                if not abs_path.exists():
                    missing_files += 1
                    continue
                try:
                    abs_path.unlink()
                    deleted_files += 1
                except Exception:
                    skipped_files += 1

            print(
                f"File cleanup summary: deleted={deleted_files}, skipped={skipped_files}, missing={missing_files}, unsafe(outside outputs)={unsafe_files}"
            )

        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.")
        session.rollback()
        return 130
    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        session.rollback()
        return 1
    finally:
        try:
            session.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
