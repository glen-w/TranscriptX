"""Cache invalidation, terminal journal, handle-result storage — Phase A extract."""

from __future__ import annotations

from transcriptx.web.services.run_cleanup import handles as handle_store
from transcriptx.web.services.run_cleanup import journal
from transcriptx.web.services.run_cleanup.faults import fault_point
from transcriptx.web.services.run_cleanup.models import CleanupResult, CleanupStatus


def finalise_operation(
    host,
    *,
    handle_token: str,
    session_id: str,
    result: CleanupResult,
    operation_id: str,
    mutation_started: bool,
) -> CleanupResult:
    """Phase-aware finalisation: never raises; always best-effort through all steps."""
    warnings = list(result.warnings)
    errors = list(result.errors)
    status = result.status
    # 1. Cache invalidation when mutation started (even if later steps fail)
    try:
        if mutation_started:
            fault_point("before_cache_invalidation")
            for w in host._invalidate_caches():
                warnings.append(w)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"cache invalidation failed: {exc}")
    # 2. Terminal journal update (may be absent when no journal created)
    try:
        if operation_id:
            fault_point("before_terminal_journal")
            # Never write SUCCESS if journal durability cannot be confirmed.
            write_status = status
            if status is CleanupStatus.SUCCESS:
                # Re-check target vector immediately before terminal write.
                try:
                    derived = host._status_from_loaded_operation(operation_id)
                    if derived is not CleanupStatus.SUCCESS:
                        write_status = derived
                        status = derived
                except Exception as exc:  # noqa: BLE001
                    write_status = CleanupStatus.PARTIAL
                    status = CleanupStatus.PARTIAL
                    errors.append(f"could not derive terminal status: {exc}")
            dur = journal.update_operation_status(
                host.state_dir, operation_id, write_status.value
            )
            if dur.outcome is journal.DirFsyncOutcome.FAILED:
                errors.append(f"terminal journal durability failed: {dur.message}")
                if status is CleanupStatus.SUCCESS:
                    status = CleanupStatus.PARTIAL
    except Exception as exc:  # noqa: BLE001
        errors.append(f"terminal journal update failed: {exc}")
        if status is CleanupStatus.SUCCESS:
            status = CleanupStatus.PARTIAL
    final = CleanupResult(
        operation_id=result.operation_id,
        plan_id=result.plan_id,
        mode=result.mode,
        status=status,
        targets=result.targets,
        warnings=tuple(warnings),
        errors=tuple(errors),
        visible_removed_count=result.visible_removed_count,
        physically_deleted_count=result.physically_deleted_count,
    )
    # 3. Handle completion — on failure leave claimed/in_progress (never re-issue)
    try:
        fault_point("before_terminal_result_store")
        handle_store.store_result(handle_token, session_id, final)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"handle result store failed: {exc}")
        final = CleanupResult(
            operation_id=final.operation_id,
            plan_id=final.plan_id,
            mode=final.mode,
            status=final.status,
            targets=final.targets,
            warnings=tuple(warnings),
            errors=final.errors,
            visible_removed_count=final.visible_removed_count,
            physically_deleted_count=final.physically_deleted_count,
        )
    return final


def invalidate_caches(host) -> list[str]:
    warnings: list[str] = []
    if host._cache_invalidator is not None:
        try:
            host._cache_invalidator()
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"cache invalidation failed: {exc}")
        return warnings
    try:
        from transcriptx.web.services.artifact_service import clear_artifact_caches

        clear_artifact_caches()
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"artifact cache invalidation failed: {exc}")
    try:
        from transcriptx.web.cache_helpers import clear_run_listing_caches

        clear_run_listing_caches()
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"run listing cache invalidation failed: {exc}")
    return warnings
