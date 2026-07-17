"""Shared journal persistence helpers — Phase A extract."""

from __future__ import annotations

from typing import Mapping

from transcriptx.web.services.run_cleanup import journal
from transcriptx.web.services.run_cleanup.models import CleanupPlan, CleanupTarget


def persist_target_state(
    host,
    operation_id: str,
    *,
    canonical_path: str,
    state: str,
    staging_path: str | None = None,
    staged_dev: int | None = None,
    staged_ino: int | None = None,
    extra: Mapping[str, object] | None = None,
    require_durable: bool = False,
) -> journal.DirFsyncResult | None:
    """Best-effort journal target update. Returns None on hard failure."""
    try:
        dur = journal.update_target_state(
            host.state_dir,
            operation_id,
            canonical_path=canonical_path,
            state=state,
            staging_path=staging_path,
            staged_dev=staged_dev,
            staged_ino=staged_ino,
            extra=extra,
        )
    except Exception:
        if require_durable:
            raise
        return None
    if require_durable and dur.outcome is journal.DirFsyncOutcome.FAILED:
        raise journal.JournalDurabilityError(dur.message or "journal fsync failed")
    return dur


def new_journaled_operation(
    host, plan: CleanupPlan, to_mutate: list[CleanupTarget]
) -> str:
    last_exc: Exception | None = None
    for _ in range(5):
        operation_id = journal.new_operation_id()
        staging_map = {
            t.canonical_path: str(
                journal.intended_staging_path(
                    host._output_root_for_target(t), operation_id, t
                )
            )
            for t in to_mutate
        }
        try:
            journal.write_operation(
                host.state_dir,
                operation_id=operation_id,
                plan=CleanupPlan(
                    plan_id=plan.plan_id,
                    mode=plan.mode,
                    policy_version=plan.policy_version,
                    created_at_iso=plan.created_at_iso,
                    roots=plan.roots,
                    candidates=tuple(to_mutate),
                    retained=plan.retained,
                    exclusions=plan.exclusions,
                    warnings=plan.warnings,
                    blocking_errors=plan.blocking_errors,
                    can_execute=plan.can_execute,
                ),
                staging_destinations=staging_map,
            )
            return operation_id
        except FileExistsError as exc:
            last_exc = exc
            continue
    raise RuntimeError(f"could not allocate operation_id: {last_exc}")
