"""DTOs for prepared, planned, and executed pipeline phases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from transcriptx.core.domain.canonical_transcript import CanonicalTranscript
from transcriptx.core.pipeline.contracts import (
    ExecutionPlan,
    PersistenceOutcome,
    RunConfigSnapshot,
    RunStatus,
    TranscriptIdentity,
)


@dataclass(frozen=True)
class PreparedTranscript:
    transcript_path: str
    canonical: CanonicalTranscript
    transcript_identity: TranscriptIdentity
    transcript_key: str
    run_id: str
    source_basename: str
    slug: str


@dataclass(frozen=True)
class PreparedWorkspace:
    output_dir: str
    config: Any
    config_snapshot: RunConfigSnapshot
    draft_override_used: bool


@dataclass(frozen=True)
class PlannedRun:
    dag_pipeline: Any
    plan: ExecutionPlan
    requirements_resolver: Any
    review: Dict[str, Any]
    run_report: Any
    execution_plan_outcome: PersistenceOutcome


@dataclass(frozen=True)
class ExecutedRun:
    dag_results: Dict[str, Any]
    context: Optional[Any]
    named_speaker_count: int
    execution_status: RunStatus
    summary: Dict[str, Any]
