"""Filesystem adapter for DAG execution plans."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.pipeline.contracts import (
    ErrorKind,
    ExecutionPlan,
    PersistenceOutcome,
)
from transcriptx.core.pipeline.ports import ExecutionPlanStore
from transcriptx.core.utils.artifact_writer import write_json


class FileExecutionPlanStore(ExecutionPlanStore):
    def save(self, plan: ExecutionPlan, output_dir: str) -> PersistenceOutcome:
        try:
            manifest_dir = Path(output_dir) / ".transcriptx"
            manifest_dir.mkdir(parents=True, exist_ok=True)
            write_json(
                manifest_dir / "execution_plan.json",
                {
                    "requested": plan.requested,
                    "runnable": plan.runnable,
                    "dependency_added": plan.dependency_added,
                    "blocked": plan.blocked,
                    "skipped_preflight": plan.skipped_preflight,
                    "deterministic_order": plan.deterministic_order,
                    "plan_hash": plan.plan_hash,
                    "schema_version": plan.schema_version,
                },
                indent=2,
                ensure_ascii=False,
            )
            return PersistenceOutcome(
                name="execution_plan", success=True, severity="optional"
            )
        except Exception as e:
            return PersistenceOutcome(
                name="execution_plan",
                success=False,
                severity="optional",
                error_kind=ErrorKind.PERSISTENCE,
                error_message=str(e),
            )
