"""Pydantic models for voice privacy and canonical evidence (Stages 0–3)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from transcriptx.core.speaker_profiles.errors import SpeakerProfileContractError
from transcriptx.core.speaker_profiles.voice.versioning import (
    BOOTSTRAP_MAX_LINKS_MAX,
    BOOTSTRAP_MAX_LINKS_MIN,
    DEFAULT_BOOTSTRAP_MAX_LINKS,
    OPERATOR_SETTINGS_SCHEMA_ID,
    PRIVACY_SETTINGS_SCHEMA_ID,
    VOICE_DECISION_SCHEMA_ID,
    VOICE_EMBEDDING_SCHEMA_ID,
    VOICE_SAMPLE_SCHEMA_ID,
    VOICE_SCHEMA_VERSION,
)

EvidenceTrust = Literal["manual", "suggestion_assisted", "promoted", "imported"]
EligibilityState = Literal[
    "eligible",
    "ineligible_trust",
    "ineligible_review",
    "ineligible_missing_source",
    "ineligible_archived",
    "ineligible_ignored",
    "ineligible_fingerprint",
]


class VoicePrivacySettingsV1(BaseModel):
    """Sole activation and consent authority for local voice matching.

    No parallel config.json / env enable flag may disagree with this file.
    ``TRANSCRIPTX_VOICE_PRIVACY_DEFAULT_ENABLED`` only seeds the missing-file
    default; it never overrides an on-disk settings document.
    """

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = VOICE_SCHEMA_VERSION
    schema_id: Literal["voice_privacy_settings.v1"] = PRIVACY_SETTINGS_SCHEMA_ID  # type: ignore[assignment]
    enabled: bool = False
    consent_at: Optional[str] = None
    consent_actor: Optional[str] = None
    privacy_notice_version: str
    revoked_at: Optional[str] = None
    wipe_required: bool = False

    @model_validator(mode="after")
    def _check_invariants(self) -> VoicePrivacySettingsV1:
        if self.schema_id != PRIVACY_SETTINGS_SCHEMA_ID:
            raise SpeakerProfileContractError(
                f"schema_id must be {PRIVACY_SETTINGS_SCHEMA_ID!r}"
            )
        if not self.privacy_notice_version.strip():
            raise SpeakerProfileContractError(
                "privacy_notice_version must be non-empty"
            )
        if self.enabled and not self.consent_at:
            raise SpeakerProfileContractError(
                "enabled voice matching requires consent_at"
            )
        if self.enabled and self.revoked_at:
            raise SpeakerProfileContractError(
                "enabled settings cannot carry revoked_at"
            )
        return self


class VoiceOperatorSettingsV1(BaseModel):
    """Durable operator knobs for voice enrolment (not consent / activation).

    Survives privacy revoke + evidence wipe. Consent remains solely in
    ``privacy.voice_settings.json``.
    """

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = VOICE_SCHEMA_VERSION
    schema_id: Literal["voice_operator_settings.v1"] = OPERATOR_SETTINGS_SCHEMA_ID  # type: ignore[assignment]
    bootstrap_max_links: int = DEFAULT_BOOTSTRAP_MAX_LINKS
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None

    @model_validator(mode="after")
    def _check_invariants(self) -> VoiceOperatorSettingsV1:
        if self.schema_id != OPERATOR_SETTINGS_SCHEMA_ID:
            raise SpeakerProfileContractError(
                f"schema_id must be {OPERATOR_SETTINGS_SCHEMA_ID!r}"
            )
        if not (
            BOOTSTRAP_MAX_LINKS_MIN
            <= self.bootstrap_max_links
            <= BOOTSTRAP_MAX_LINKS_MAX
        ):
            raise SpeakerProfileContractError(
                "bootstrap_max_links must be between "
                f"{BOOTSTRAP_MAX_LINKS_MIN} and {BOOTSTRAP_MAX_LINKS_MAX}"
            )
        return self


class VoiceSampleV1(BaseModel):
    """Canonical voice sample metadata (evidence, not identity)."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    version: Literal[1] = VOICE_SCHEMA_VERSION
    schema_id: Literal["voice_sample.v1"] = VOICE_SAMPLE_SCHEMA_ID  # type: ignore[assignment]
    sample_id: str
    profile_id: str
    source_link_id: str
    source_link_fingerprint: str
    source_link_content_sha256: Optional[str] = None
    managed_transcript_id: str
    local_speaker_key: str
    occurrence_fingerprint: str
    audio_stat_fingerprint: str
    audio_content_sha256: str
    clip_start_us: int
    clip_end_us: int
    model_generation_id: str
    preprocessing_policy_id: str
    quality_policy_id: str
    trust_level: EvidenceTrust
    eligibility_state: EligibilityState
    ownership_provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    eligibility_metrics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check(self) -> VoiceSampleV1:
        if self.schema_id != VOICE_SAMPLE_SCHEMA_ID:
            raise SpeakerProfileContractError("invalid voice_sample schema_id")
        if self.clip_end_us <= self.clip_start_us:
            raise SpeakerProfileContractError("clip_end_us must exceed clip_start_us")
        return self


class VoiceEmbeddingV1(BaseModel):
    """Canonical embedding metadata; vector bytes live beside in vectors/."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    version: Literal[1] = VOICE_SCHEMA_VERSION
    schema_id: Literal["voice_embedding.v1"] = VOICE_EMBEDDING_SCHEMA_ID  # type: ignore[assignment]
    embedding_id: str
    sample_id: str
    profile_id: str
    source_link_id: str
    source_link_fingerprint: str
    embedding_schema_version: str
    model_id: str
    model_revision: str
    model_generation_id: str
    preprocessing_policy_id: str
    quality_policy_id: str
    trust_level: EvidenceTrust
    eligibility_state: EligibilityState
    vector_sha256: str
    nbytes: int
    dimension: int
    dtype: Literal["<f4"] = "<f4"
    runtime_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str

    @model_validator(mode="after")
    def _check(self) -> VoiceEmbeddingV1:
        if self.schema_id != VOICE_EMBEDDING_SCHEMA_ID:
            raise SpeakerProfileContractError("invalid voice_embedding schema_id")
        if self.dimension <= 0 or self.nbytes <= 0:
            raise SpeakerProfileContractError("dimension/nbytes must be positive")
        return self


DecisionKind = Literal["accept", "reject", "dismiss", "promote"]
DecisionScope = Literal["occurrence_profile", "occurrence_all"]


class VoiceMatchDecisionV1(BaseModel):
    """Durable accept/reject/dismiss/promote decision (not a live-link status)."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    version: Literal[1] = VOICE_SCHEMA_VERSION
    schema_id: Literal["voice_match_decision.v1"] = VOICE_DECISION_SCHEMA_ID  # type: ignore[assignment]
    decision_id: str
    decision_kind: DecisionKind
    scope: DecisionScope
    managed_transcript_id: str
    local_speaker_key: str
    occurrence_fingerprint: str
    candidate_profile_id: Optional[str] = None
    suggestion_id: Optional[str] = None
    suggestion_digest: Optional[str] = None
    model_generation_id: Optional[str] = None
    threshold_policy_id: Optional[str] = None
    supersedes_decision_id: Optional[str] = None
    reference_count_at_decision: Optional[int] = None
    reference_corpus_digest: Optional[str] = None
    confidence_category: Optional[str] = None
    created_at: str
    actor: str = "user"

    @model_validator(mode="after")
    def _check(self) -> VoiceMatchDecisionV1:
        if self.schema_id != VOICE_DECISION_SCHEMA_ID:
            raise SpeakerProfileContractError("invalid voice_match_decision schema_id")
        return self
