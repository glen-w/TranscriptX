"""Reconcile phase: slug index, path-cache invalidation, temp cleanup."""

from __future__ import annotations

from transcriptx.core.utils._path_cache import invalidate_path_cache
from transcriptx.core.utils.rename.finalize import cleanup_abandoned_temps
from transcriptx.core.utils.rename.journal import RenameJournalRecord
from transcriptx.core.utils.rename.outcome import RenameError


def _run_reconcile_phase(
    journal: RenameJournalRecord,
    warnings: list[str],
    errors: list[RenameError],
) -> tuple[bool, str | None, str | None]:
    """Slug reconcile + path-cache invalidation + abandoned-temp cleanup.

    Returns (reconciliation_succeeded, old_slug, new_slug). Mutates
    journal/warnings/errors in place.
    """
    old_slug = journal.old_slug or journal.planned_old_slug
    new_slug = journal.new_slug or journal.planned_new_slug
    reconciliation_succeeded = True
    from transcriptx.core.utils.slug_manager import (
        SlugConflictError,
        update_index_after_transcript_rename,
    )

    try:
        old_slug, new_slug = update_index_after_transcript_rename(
            journal.old_transcript_path, journal.new_transcript_path
        )
        journal.old_slug = old_slug
        journal.new_slug = new_slug
    except SlugConflictError as e:
        reconciliation_succeeded = False
        err = RenameError(code="slug_conflict", message=str(e), phase="reconcile")
        errors.append(err)
        journal.errors.append(
            {"code": err.code, "message": err.message, "phase": err.phase}
        )
        warnings.append(f"Slug index reconciliation failed: {e}")
    except Exception as e:
        reconciliation_succeeded = False
        err = RenameError(
            code="slug_reconciliation_failed", message=str(e), phase="reconcile"
        )
        errors.append(err)
        journal.errors.append(
            {"code": err.code, "message": err.message, "phase": err.phase}
        )
        warnings.append(f"Slug index reconciliation failed: {e}")

    try:
        invalidate_path_cache(journal.old_transcript_path)
        invalidate_path_cache(journal.new_transcript_path)
    except Exception as e:
        err = RenameError(
            code="cache_invalidation_failed",
            message=str(e),
            phase="reconcile",
        )
        errors.append(err)
        journal.errors.append(
            {"code": err.code, "message": err.message, "phase": err.phase}
        )
        reconciliation_succeeded = False

    cleanup_abandoned_temps(recorded_temps=journal.recorded_temps)
    return reconciliation_succeeded, old_slug, new_slug
