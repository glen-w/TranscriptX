"""
Canonical Corrections Studio schema: enums, snapshot entities, events, provenance.

Engine types (Candidate, Decision) are not defined here — see compile_studio_to_engine_apply.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Vocabulary (string enums — Python 3.10 compatible)
# ---------------------------------------------------------------------------


class ReviewAction(str, Enum):
    accept = "accept"
    reject = "reject"
    skip = "skip"
    learn = "learn"


class ReviewStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    skipped = "skipped"
    superseded = "superseded"


class ApplyScope(str, Enum):
    all = "all"
    selected = "selected"


class LearnIntent(str, Enum):
    none = "none"
    create_rule = "create_rule"


class RuleLifecycleState(str, Enum):
    suggested = "suggested"
    drafted = "drafted"
    session_active = "session_active"
    promoted_global = "promoted_global"
    disabled = "disabled"


class ConflictResolutionPolicy(str, Enum):
    inspect_only = "inspect_only"
    first_wins = "first_wins"
    user_override = "user_override"


class StalenessStatus(str, Enum):
    ok = "ok"
    stale_generation = "stale_generation"
    incompatible_transcript = "incompatible_transcript"


# ---------------------------------------------------------------------------
# Snapshot entities
# ---------------------------------------------------------------------------


class GenerationManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transcript_identity_hash: str
    corrections_config_fingerprint: str = ""
    detector_version: str
    memory_rule_fingerprint: str = ""
    speaker_map_fingerprint: Optional[str] = None
    tool_build_id: Optional[str] = None


class StudioGenerationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation_id: int
    generation_manifest: GenerationManifest
    generation_manifest_hash: str
    candidate_ids: List[str] = Field(default_factory=list)
    completed_at: str


class StudioOccurrence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str
    stable_occurrence_key: str
    span: Optional[tuple[int, int]] = None
    snippet: str = ""
    speaker: Optional[str] = None
    time_start: Optional[float] = None
    time_end: Optional[float] = None
    segment_index: int = -1

    @field_validator("span", mode="before")
    @classmethod
    def _span(cls, v: Any) -> Optional[tuple[int, int]]:
        if v is None:
            return None
        if isinstance(v, (list, tuple)) and len(v) == 2:
            return (int(v[0]), int(v[1]))
        raise ValueError("span must be a 2-item sequence")


class StudioCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    generation_id: int
    kind: str
    wrong_text: str
    right_text: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    rule_id: Optional[str] = None
    occurrences: List[StudioOccurrence] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.pending


class StudioReviewRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    generation_id: int
    candidate_id: str
    review_action: ReviewAction
    apply_scope: ApplyScope = ApplyScope.all
    selected_occurrence_keys: List[str] = Field(default_factory=list)
    learn_intent: Optional[LearnIntent] = None
    learn_rule_id: Optional[str] = None
    recorded_at: str
    event_sequence: int


class StudioRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    rule_type: str
    wrong_variants: List[str] = Field(default_factory=list)
    replacement_text: str = ""
    scope: str = "global"
    confidence: float = 0.0
    auto_apply: bool = False
    conditions_json: Optional[Dict[str, Any]] = None
    is_person_name: bool = False
    lifecycle: RuleLifecycleState = RuleLifecycleState.session_active


class ConflictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflict_id: str
    granularity: Literal["occurrence", "span", "candidate"]
    segment_id: str
    span_start: int = -1
    span_end: int = -1
    candidate_ids: List[str] = Field(default_factory=list)
    policy: ConflictResolutionPolicy = ConflictResolutionPolicy.inspect_only
    reason_code: str = ""


class ConflictSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflicts: List[ConflictRecord] = Field(default_factory=list)


class StudioSessionDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    studio_schema_version: int = 1
    session_id: str
    transcript_path: str
    recorded_transcript_identity_hash: str
    current_generation_id: Optional[int] = None
    staleness_status: StalenessStatus = StalenessStatus.ok
    lineage_parent_session_id: Optional[str] = None
    current_generation: Optional[StudioGenerationRecord] = None
    candidates: List[StudioCandidate] = Field(default_factory=list)
    review_records: List[StudioReviewRecord] = Field(default_factory=list)
    rules: Dict[str, StudioRule] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    status: str = "active"

    # Ephemeral / UI cache (not persisted in v1 hot path unless needed)
    candidates_stale: bool = False


# ---------------------------------------------------------------------------
# Export provenance
# ---------------------------------------------------------------------------


class ExportProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    generation_id: int
    transcript_identity_hash: str
    generation_manifest_hash: str
    generation_manifest: Optional[GenerationManifest] = None
    studio_schema_version: int
    compiler_version: str = ""
    detector_version: str = ""
    applied_candidate_ids: List[str] = Field(default_factory=list)
    rejected_candidate_ids: List[str] = Field(default_factory=list)
    review_summary_counts: Dict[str, int] = Field(default_factory=dict)
    applied_occurrence_keys: List[str] = Field(default_factory=list)
    review_actions_summary: Dict[str, int] = Field(default_factory=dict)
    conflict_digest: str = ""
    active_rules_summary: List[str] = Field(default_factory=list)
    exported_artifact_paths: List[str] = Field(default_factory=list)
    export_timestamp_utc: str
    tool_version: str = ""
    build_id: str = ""


# ---------------------------------------------------------------------------
# Event payloads (typed)
# ---------------------------------------------------------------------------


def _utc_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class SessionStartedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transcript_path: str
    recorded_transcript_identity_hash: str


class CandidatesGeneratedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation_id: int
    generation_manifest: GenerationManifest
    generation_manifest_hash: str
    candidate_ids: List[str]
    candidates: List[Dict[str, Any]] = Field(default_factory=list)


class ReviewRecordedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation_id: int
    candidate_id: str
    review_action: ReviewAction
    apply_scope: ApplyScope = ApplyScope.all
    selected_occurrence_keys: List[str] = Field(default_factory=list)
    learn_intent: Optional[LearnIntent] = None
    learn_rule_id: Optional[str] = None


class PreviewComputedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation_id: int
    applied_count: int = 0
    total_accepted: int = 0


class ExportCompletedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation_id: int
    export_paths: List[str] = Field(default_factory=list)
    provenance_path: Optional[str] = None


class StudioEventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    event_type: Literal[
        "session_started",
        "candidates_generated",
        "review_recorded",
        "preview_computed",
        "export_completed",
        "rule_state_changed",
        "session_forked",
        "staleness_detected",
        "incompatible_transcript_detected",
    ]
    event_sequence: int
    timestamp: str = Field(default_factory=_utc_z)
    payload_schema_version: int = 1
    generation_id: Optional[int] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
