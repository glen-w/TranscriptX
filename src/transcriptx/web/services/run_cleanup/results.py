"""Status derivation and result helpers for run cleanup.

Phase B2: authoritative SUCCESS/PARTIAL reduction — no SUCCESS-on-any-success.
"""

from __future__ import annotations

from pathlib import Path

from transcriptx.web.services.run_cleanup import journal
from transcriptx.web.services.run_cleanup.models import (
    CLEANUP_POLICY_VERSION,
    JOURNAL_SCHEMA_VERSION,
    CleanupStatus,
)


def summarize_status(
    *,
    visible_removed: int,
    physically_deleted: int,
    planned: int,
    lock_skips: int,
    errors: list[str],
    has_staged_remnant: bool,
    mutation_started: bool,
) -> CleanupStatus:
    if mutation_started:
        if (
            visible_removed == planned
            and physically_deleted == planned
            and not errors
            and not lock_skips
            and not has_staged_remnant
        ):
            return CleanupStatus.SUCCESS
        return CleanupStatus.PARTIAL
    if lock_skips:
        return CleanupStatus.PARTIAL
    if errors:
        return CleanupStatus.FAILED_BEFORE_MUTATION
    return CleanupStatus.NOOP


def status_from_journal_targets(targets: list[dict]) -> CleanupStatus:
    """Derive operation status from the complete journal target-state vector.

    SUCCESS requires every target to be ``physical_deleted``. Mixed outcomes
    (including any lock skip, staging failure, or ``external_disappeared``)
    are PARTIAL. ``external_disappeared`` is never treated as a SUCCESS fact.
    """
    if not targets:
        return CleanupStatus.NOOP
    states = [str(t.get("state") or "") for t in targets]
    deleted = {"physical_deleted"}
    skip = journal.TERMINAL_SKIP_TARGET_STATES
    mid_flight = journal.PENDING_TARGET_STATES - {"planned"}

    if any(s in mid_flight for s in states):
        return CleanupStatus.PARTIAL
    if any(s == "planned" for s in states):
        if any(s in deleted for s in states):
            return CleanupStatus.PARTIAL
        return CleanupStatus.FAILED_BEFORE_MUTATION
    if any(s not in deleted | skip | {"external_disappeared"} for s in states):
        return CleanupStatus.PARTIAL
    if any(s == "external_disappeared" for s in states):
        # Complete disappearance is not a verified physical delete.
        return CleanupStatus.PARTIAL
    if any(s in skip for s in states):
        if any(s in deleted for s in states):
            return CleanupStatus.PARTIAL
        return CleanupStatus.NOOP
    if states and all(s in deleted for s in states):
        return CleanupStatus.SUCCESS
    return CleanupStatus.NOOP


def status_from_loaded_operation(state_dir: Path, operation_id: str) -> CleanupStatus:
    data = journal.load_operation(
        state_dir,
        operation_id,
        expected_policy_version=CLEANUP_POLICY_VERSION,
        expected_schema_version=JOURNAL_SCHEMA_VERSION,
    )
    if data is None:
        raise FileNotFoundError(f"cleanup journal missing: {operation_id}")
    return status_from_journal_targets(list(data.get("targets") or []))
