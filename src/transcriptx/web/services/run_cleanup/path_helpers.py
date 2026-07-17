"""Shared path/root helpers used by Phase A orchestration modules."""

from __future__ import annotations

from pathlib import Path

from transcriptx.web.services.run_cleanup.models import (
    CleanupPlan,
    CleanupTarget,
    RootIdentity,
    SubjectType,
)
from transcriptx.web.services.run_cleanup.root_validator import OutputRootValidator
from transcriptx.web.services.run_cleanup.staging import StagingUnsafeError


def output_root_for_target(host, target: CleanupTarget) -> Path:
    if target.subject_type is SubjectType.group:
        return host.group_outputs_dir
    return host.outputs_dir


def planned_root_for_target(plan: CleanupPlan, target: CleanupTarget) -> RootIdentity:
    kind = target.subject_type
    for root in plan.roots:
        if root.kind is kind:
            return root
    raise StagingUnsafeError(f"no planned root for {kind}")


def validate_roots(host) -> tuple[list[RootIdentity], list[str]]:
    runtime = getattr(host, "_runtime", None)
    if runtime is not None:
        protected = runtime.protected_paths()
    else:
        protected = host._protected_paths()
    return OutputRootValidator.validate(
        host.outputs_dir,
        host.group_outputs_dir,
        protected,
        project_root=host.project_root,
        data_dir=host.data_dir,
        state_dir=host.state_dir,
    )
