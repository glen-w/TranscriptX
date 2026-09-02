"""
Compact run-status presentation for Overview / Insights.

Keeps artifact filesystem health and execution outcomes as separate fields.
User-facing labels may aggregate them (e.g. Completed with issues) without
redefining healthy storage as unhealthy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from transcriptx.core.pipeline.manifest_loader import load_run_results
from transcriptx.core.pipeline.run_outcome_truth import (
    project_canonical_outcomes,
    project_group_outcomes,
)
from transcriptx.web.services.artifact_service import ArtifactService

ArtifactHealthStatus = Literal["healthy", "partial", "missing", "unknown"]
ExecutionStatus = Literal[
    "succeeded",
    "completed_with_issues",
    "failed",
    "partial",
    "in_progress",
    "unknown",
    "not_available",
]


@dataclass(frozen=True)
class TechnicalDetail:
    source: Literal["artifact_health", "execution"]
    message: str
    module_id: str | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class RunStatusSummary:
    artifact_health: ArtifactHealthStatus
    execution_status: ExecutionStatus
    failed_count: int = 0
    skipped_count: int = 0
    blocked_count: int = 0
    user_facing_label: str = "Status unknown"
    technical_details: tuple[TechnicalDetail, ...] = field(default_factory=tuple)

    @property
    def has_execution_issues(self) -> bool:
        return self.failed_count > 0 or self.blocked_count > 0


def _map_artifact_health(health: dict[str, Any] | None) -> ArtifactHealthStatus:
    if not health:
        return "unknown"
    status = health.get("status")
    if status == "error" or health.get("errors"):
        return "missing"
    if status == "warning" or health.get("warnings"):
        return "partial"
    if status == "ok" or status == "healthy":
        return "healthy"
    # Default when status unset but no errors
    if not health.get("errors") and not health.get("warnings"):
        return "healthy"
    return "unknown"


def _user_facing_label(
    artifact_health: ArtifactHealthStatus,
    execution_status: ExecutionStatus,
    *,
    failed_count: int,
) -> str:
    if execution_status == "in_progress":
        return "In progress"
    if artifact_health == "missing":
        return "Artifacts incomplete"
    if execution_status == "failed" and failed_count:
        if artifact_health in {"healthy", "partial"}:
            return "Completed with issues"
        return "Run failed"
    if execution_status == "completed_with_issues":
        return "Completed with issues"
    if execution_status == "partial":
        return "Partial success"
    if artifact_health == "partial":
        return "Artifacts partial"
    if execution_status == "succeeded" and artifact_health == "healthy":
        return "Completed"
    if execution_status == "not_available":
        if artifact_health == "healthy":
            return "Artifacts healthy"
        return "Status unknown"
    return "Status unknown"


def build_run_status_summary(
    run_root: Path,
    *,
    health: dict[str, Any] | None = None,
    run_results: dict[str, Any] | None = None,
) -> RunStatusSummary:
    root = Path(run_root)
    health_payload = (
        health if health is not None else ArtifactService.check_run_health(root)
    )
    artifact_health = _map_artifact_health(health_payload)

    details: list[TechnicalDetail] = []
    for err in health_payload.get("errors") or []:
        details.append(TechnicalDetail(source="artifact_health", message=str(err)))
    for warn in health_payload.get("warnings") or []:
        details.append(TechnicalDetail(source="artifact_health", message=str(warn)))

    failed = skipped = blocked = 0
    outcomes: list[Any] = []
    rr = run_results
    if rr is None:
        rr_path = root / "run_results.json"
        if rr_path.exists():
            try:
                rr = load_run_results(rr_path)
            except Exception:
                rr = None

    if rr:
        if str(rr.get("run_status") or "").strip().lower() == "running":
            return RunStatusSummary(
                artifact_health=artifact_health,
                execution_status="in_progress",
                user_facing_label=_user_facing_label(
                    artifact_health, "in_progress", failed_count=0
                ),
                technical_details=tuple(details),
            )
        try:
            if (root / "group_member_runs.json").exists():
                try:
                    outcomes = list(project_group_outcomes(root).group_outcomes)
                except Exception:
                    outcomes = list(project_canonical_outcomes(rr))
            else:
                outcomes = list(project_canonical_outcomes(rr))
        except Exception:
            outcomes = []

    for row in outcomes:
        status = getattr(row, "status", None)
        if status == "failed":
            failed += 1
            msg = getattr(row, "reason", None) or "failed"
            details.append(
                TechnicalDetail(
                    source="execution",
                    message=str(msg),
                    module_id=getattr(row, "module_id", None),
                    error_code=getattr(row, "error_code", None),
                )
            )
        elif status == "skipped":
            skipped += 1
        elif status == "blocked":
            blocked += 1
            details.append(
                TechnicalDetail(
                    source="execution",
                    message=str(getattr(row, "reason", None) or "blocked"),
                    module_id=getattr(row, "module_id", None),
                    error_code=getattr(row, "error_code", None),
                )
            )

    if rr is None:
        execution_status: ExecutionStatus = "not_available"
    elif failed and not any(
        getattr(o, "status", None) == "succeeded" for o in outcomes
    ):
        execution_status = "failed"
    elif failed or blocked:
        execution_status = "completed_with_issues"
    elif skipped and not any(
        getattr(o, "status", None) == "succeeded" for o in outcomes
    ):
        execution_status = "partial"
    else:
        execution_status = "succeeded"

    label = _user_facing_label(artifact_health, execution_status, failed_count=failed)
    if failed == 1 and execution_status == "completed_with_issues":
        label = "1 module failed"
    elif failed > 1 and execution_status == "completed_with_issues":
        label = f"{failed} modules failed"

    return RunStatusSummary(
        artifact_health=artifact_health,
        execution_status=execution_status,
        failed_count=failed,
        skipped_count=skipped,
        blocked_count=blocked,
        user_facing_label=label,
        technical_details=tuple(details),
    )


def module_outcome_state(
    run_root: Path | None,
    module_id: str,
    *,
    run_results: dict[str, Any] | None = None,
) -> Literal["failed", "skipped", "blocked", "succeeded", "not_run", "unknown"]:
    if run_root is None:
        return "unknown"
    rr = run_results
    if rr is None:
        rr_path = Path(run_root) / "run_results.json"
        if not rr_path.exists():
            return "not_run"
        try:
            rr = load_run_results(rr_path)
        except Exception:
            return "unknown"
    try:
        for row in project_canonical_outcomes(rr):
            if row.module_id == module_id:
                if row.status in {"failed", "skipped", "blocked", "succeeded"}:
                    return row.status  # type: ignore[return-value]
                return "unknown"
    except Exception:
        return "unknown"
    return "not_run"
