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


class FuzzySkippedReason(str, Enum):
    disabled = "disabled"
    no_speaker_map = "no_speaker_map"
    zero_map_entries = "zero_map_entries"
    zero_named_speakers = "zero_named_speakers"
    not_applicable = "not_applicable"


class CandidateSource(str, Enum):
    detector_memory = "detector_memory"
    detector_acronym = "detector_acronym"
    detector_consistency = "detector_consistency"
    detector_fuzzy = "detector_fuzzy"
    llm_discovery = "llm_discovery"
    viewer_manual = "viewer_manual"


class GenerationOrigin(str, Enum):
    """How the current generation was created."""

    detector = "detector"
    manual_seed = "manual_seed"


class EvidenceStrength(str, Enum):
    strong = "strong"
    moderate = "moderate"
    weak = "weak"
    disputed = "disputed"


class EvidenceSignal(str, Enum):
    memory_match = "memory_match"
    repeated_form = "repeated_form"
    speaker_context = "speaker_context"
    acronym_pattern = "acronym_pattern"
    cross_segment_consistency = "cross_segment_consistency"
    model_suggestion = "model_suggestion"
    homophone_pattern = "homophone_pattern"
    viewer_edit = "viewer_edit"


class CandidateEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    strength: EvidenceStrength = EvidenceStrength.moderate
    signals: List[EvidenceSignal] = Field(default_factory=list)
    rationale: str = ""
    review_priority: Literal["high", "normal", "low", "inspect"] = "normal"
    model_certainty_label: Optional[Literal["confident", "tentative"]] = None


class LlmCandidateProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    llm_run_id: str
    prompt_version: str
    schema_version: str
    model: str
    provider: str = "ollama"
    effort: str
    llm_request_sha256: str
    chunk_index: Optional[int] = None
    validation_status: Literal["valid"] = "valid"


class ReviewMigrationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    carried: int = 0
    reset: int = 0
    orphaned_prior: int = 0


class LlmGenerationDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    attempted: bool = False
    available: bool = False
    outcome: Literal["skipped", "success", "partial", "failed", "unavailable"] = (
        "skipped"
    )
    chunks_total: int = 0
    chunks_succeeded: int = 0
    chunks_failed: int = 0
    candidates_raw: int = 0
    candidates_grounded: int = 0
    candidates_rejected: int = 0
    candidates_after_merge: int = 0
    overlapping_conflicts: int = 0
    error_code: Optional[str] = None
    budget_reason: Optional[str] = None
    review_migration: Optional[ReviewMigrationSummary] = None


# ---------------------------------------------------------------------------
# Snapshot entities
# ---------------------------------------------------------------------------


class GenerationManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transcript_identity_hash: str
    corrections_config_fingerprint: str = ""
    detector_version: str
    memory_rule_fingerprint: str = ""
    speaker_map_fingerprint: str = ""
    studio_session_rules_fingerprint: str = ""
    tool_build_id: Optional[str] = None
    llm_fingerprint: str = ""
    llm_prompt_version: str = ""
    llm_schema_version: str = ""
    context_pack_version: str = ""

    @field_validator("speaker_map_fingerprint", mode="before")
    @classmethod
    def _coerce_speaker_fp(cls, v: Any) -> str:
        return v if isinstance(v, str) else ""


class DetectorCountsByKind(BaseModel):
    """Per-detector or per-kind candidate counts."""

    model_config = ConfigDict(extra="forbid")

    memory_hit: int = 0
    acronym: int = 0
    consistency: int = 0
    fuzzy: int = 0
    ner_variant: int = 0
    manual: int = 0
    other: int = 0


class CandidateGenerationDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pre_dedupe: DetectorCountsByKind
    total_pre_dedupe: int
    post_dedupe_counts_by_kind: DetectorCountsByKind
    total_after_dedupe: int
    fuzzy_enabled: bool
    fuzzy_similarity_threshold: float = 0.85
    consistency_similarity_threshold: float = 0.0
    known_acronym_count: int = 0
    known_org_phrase_count: int = 0
    fuzzy_named_speaker_count: int = 0
    fuzzy_skipped_reason: FuzzySkippedReason
    observed_named_speaker_count: int = 0
    llm: Optional[LlmGenerationDiagnostics] = None


class StudioGenerationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation_id: int
    generation_manifest: GenerationManifest
    generation_manifest_hash: str
    candidate_ids: List[str] = Field(default_factory=list)
    completed_at: str
    generation_diagnostics: Optional[CandidateGenerationDiagnostics] = None
    generation_origin: GenerationOrigin = GenerationOrigin.detector


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
    sources: List[CandidateSource] = Field(default_factory=list)
    evidence: Optional[CandidateEvidence] = None
    llm_provenance: Optional[LlmCandidateProvenance] = None
    semantic_identity_key: str = ""


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
    review_target_text: Optional[str] = None
    recorded_at: str
    event_sequence: int
    migrated_from_generation_id: Optional[int] = None


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
    generation_inputs_stale: bool = False
    last_generation_commit_aborted: bool = False
    last_generation_abort_reason: str = ""


class StudioTranscriptSummary(BaseModel):
    """One row for the Corrections Studio transcript picker."""

    model_config = ConfigDict(extra="forbid")

    path: str
    base_name: str
    segment_count: int
    speaker_map_status: str = ""


class StudioReviewStats(BaseModel):
    """Review counts for the session progress bar."""

    model_config = ConfigDict(extra="forbid")

    pending: int = 0
    accepted: int = 0
    rejected: int = 0
    skipped: int = 0


class CandidateOccurrenceDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str
    segment_index: int = -1
    speaker: str = ""
    time_start: Optional[float] = None
    time_end: Optional[float] = None
    before: str = ""
    after: str = ""
    stable_occurrence_key: str = ""


class CandidateLocalDiffResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diffs: List[CandidateOccurrenceDiff] = Field(default_factory=list)


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
    llm_influenced_candidate_ids: List[str] = Field(default_factory=list)
    llm_fingerprint_at_export: str = ""


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
    diagnostics: Optional[CandidateGenerationDiagnostics] = None


class ReviewRecordedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation_id: int
    candidate_id: str
    review_action: ReviewAction
    apply_scope: ApplyScope = ApplyScope.all
    selected_occurrence_keys: List[str] = Field(default_factory=list)
    learn_intent: Optional[LearnIntent] = None
    learn_rule_id: Optional[str] = None
    review_target_text: Optional[str] = None
    migrated_from_generation_id: Optional[int] = None


class RuleStateChangedPayload(BaseModel):
    """Authoritative session-rule mutation (create / update / disable)."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    change: Literal["upsert", "disable", "enable"] = "upsert"
    rule: Optional[Dict[str, Any]] = None


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
    scoped_candidate_ids: List[str] = Field(default_factory=list)


class ManualProposedPayload(BaseModel):
    """Viewer (or API) manual correction proposal for the current generation."""

    model_config = ConfigDict(extra="forbid")

    generation_id: int
    candidate: Dict[str, Any]
    upsert: bool = False
    superseded_candidate_id: Optional[str] = None


class ManualSeedGenerationPayload(BaseModel):
    """Created when the first manual propose seeds a generation without detectors."""

    model_config = ConfigDict(extra="forbid")

    generation_id: int
    generation_origin: GenerationOrigin = GenerationOrigin.manual_seed
    transcript_identity_hash: str


class StudioPreviewStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    applied_count: int = 0
    total_accepted: int = 0


class StudioPreviewResult(BaseModel):
    """Typed return for Corrections Studio compute_preview."""

    model_config = ConfigDict(extra="forbid")

    updated_segments: List[Dict[str, Any]] = Field(default_factory=list)
    patch_log: List[Dict[str, Any]] = Field(default_factory=list)
    stats: StudioPreviewStats = Field(default_factory=StudioPreviewStats)


class StudioExportResult(BaseModel):
    """Typed return for Corrections Studio apply_and_export."""

    model_config = ConfigDict(extra="forbid")

    export_path: str
    provenance_path: str
    applied_count: int = 0


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
        "manual_proposed",
        "manual_seed_generation",
    ]
    event_sequence: int
    timestamp: str = Field(default_factory=_utc_z)
    payload_schema_version: int = 1
    generation_id: Optional[int] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
