"""Preview construction and unlocked rediscovery (Phase A extract)."""

from __future__ import annotations

from transcriptx.core.utils.logger import get_logger
from transcriptx.web.services.run_cleanup import handles as handle_store
from transcriptx.web.services.run_cleanup.models import (
    CLEANUP_POLICY_VERSION,
    CleanupMode,
    CleanupPlan,
    CleanupPreview,
    plan_to_preview,
)
from transcriptx.web.services.run_cleanup.path_helpers import validate_roots

logger = get_logger()


def build_plan(host, mode: CleanupMode) -> CleanupPlan:
    from transcriptx.web.services.run_cleanup.plan_builder import (
        build_execution_set,
        execution_set_to_plan,
    )

    roots, blocking = validate_roots(host)
    handle_store.invalidate_on_root_change(tuple(roots))
    handle_store.invalidate_on_policy_change(CLEANUP_POLICY_VERSION)
    es = build_execution_set(
        mode,
        roots,
        blocking,
        host.outputs_dir,
        host.group_outputs_dir,
    )
    return execution_set_to_plan(es)


def preview_cleanup(
    host, mode: CleanupMode, session_id: str
) -> tuple[str, CleanupPreview]:
    logger.info("cleanup preview start mode=%s", mode.value)
    plan = build_plan(host, mode)
    # May raise HandleStoreFullError when capacity is exhausted by protected entries.
    token = handle_store.create_handle(plan, session_id)
    preview = plan_to_preview(plan)
    logger.info(
        "cleanup preview ready mode=%s plan_id=%s candidates=%d retained=%d "
        "can_execute=%s",
        mode.value,
        preview.plan_id,
        preview.run_count,
        len(preview.retained),
        preview.can_execute,
    )
    return token, preview
