"""Pydantic models for speaker_profiles v1 canonical files."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from transcriptx.core.speaker_profiles.errors import SpeakerProfileContractError
from transcriptx.core.speaker_profiles.identity import canonicalize_managed_transcript_id
from transcriptx.core.speaker_profiles.versioning import (
    EVENT_SCHEMA_ID,
    LINK_SCHEMA_ID,
    OPERATION_SCHEMA_ID,
    PROFILE_SCHEMA_ID,
    SCHEMA_VERSION,
)

ProfileStatus = Literal["active", "archived", "merged"]
LinkStatus = Literal["confirmed"]
OperationPhase = Literal[
    "prepared",
    "staged",
    "transaction_committed",
    "finalized",
    "complete",
    "failed",
    "needs_repair",
]
PlanActionKind = Literal["write", "delete"]


class SpeakerProfileV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = SCHEMA_VERSION
    schema_id: Literal["transcriptx.speaker_profile.v1"] = PROFILE_SCHEMA_ID
    profile_id: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    accent_color: Optional[str] = None
    avatar_relpath: Optional[str] = None
    avatar_sha256: Optional[str] = None
    avatar_content_type: Optional[str] = None
    status: ProfileStatus = "active"
    merged_into_profile_id: Optional[str] = None
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def _check_merge_invariants(self) -> SpeakerProfileV1:
        if self.schema_id != PROFILE_SCHEMA_ID:
            raise SpeakerProfileContractError(
                f"schema_id must be {PROFILE_SCHEMA_ID!r}"
            )
        if self.status == "merged" and not self.merged_into_profile_id:
            raise SpeakerProfileContractError(
                "merged profiles require merged_into_profile_id"
            )
        if self.status != "merged" and self.merged_into_profile_id:
            raise SpeakerProfileContractError(
                "merged_into_profile_id is only valid when status is merged"
            )
        if not self.display_name.strip():
            raise SpeakerProfileContractError("display_name must be non-empty")
        from transcriptx.core.speaker_profiles.avatars import validate_avatar_field_set

        validate_avatar_field_set(
            avatar_relpath=self.avatar_relpath,
            avatar_sha256=self.avatar_sha256,
            avatar_content_type=self.avatar_content_type,
            profile_id=self.profile_id,
        )
        return self


class SpeakerProfileLinkV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = SCHEMA_VERSION
    schema_id: Literal["transcriptx.speaker_profile_link.v1"] = LINK_SCHEMA_ID
    link_id: str
    managed_transcript_id: str
    observed_transcript_relpath: str
    local_speaker_key: str
    profile_id: str
    status: LinkStatus = "confirmed"
    occurrence_fingerprint: str
    observed_label: Optional[str] = None
    created_at: str
    updated_at: str
    created_by: str = "user"
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_link_invariants(self) -> SpeakerProfileLinkV1:
        if self.schema_id != LINK_SCHEMA_ID:
            raise SpeakerProfileContractError(f"schema_id must be {LINK_SCHEMA_ID!r}")
        try:
            canonical = canonicalize_managed_transcript_id(self.managed_transcript_id)
        except SpeakerProfileContractError as exc:
            raise SpeakerProfileContractError(str(exc)) from exc
        if canonical != self.managed_transcript_id:
            raise SpeakerProfileContractError(
                "managed_transcript_id must be lowercase hyphenated UUID "
                f"(got {self.managed_transcript_id!r})"
            )
        if not self.local_speaker_key.strip():
            raise SpeakerProfileContractError("local_speaker_key must be non-empty")
        if not self.occurrence_fingerprint.startswith("occurrence_fingerprint.v1:"):
            raise SpeakerProfileContractError(
                "occurrence_fingerprint must use occurrence_fingerprint.v1 prefix"
            )
        if not self.observed_transcript_relpath.strip():
            raise SpeakerProfileContractError(
                "observed_transcript_relpath must be non-empty"
            )
        return self


class SpeakerProfileEventV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = SCHEMA_VERSION
    schema_id: Literal["transcriptx.speaker_profile_event.v1"] = EVENT_SCHEMA_ID
    event_id: str
    idempotency_id: str
    operation_idempotency_key: str
    event_type: str
    created_at: str
    actor: str = "user"
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_event_invariants(self) -> SpeakerProfileEventV1:
        if self.schema_id != EVENT_SCHEMA_ID:
            raise SpeakerProfileContractError(f"schema_id must be {EVENT_SCHEMA_ID!r}")
        if self.event_id != self.idempotency_id:
            raise SpeakerProfileContractError(
                "event_id must equal idempotency_id (filename stem)"
            )
        if not self.event_type.strip():
            raise SpeakerProfileContractError("event_type must be non-empty")
        return self


class OperationPlanActionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: PlanActionKind
    path: str
    expected_before_sha256: Optional[str] = None
    after_sha256: Optional[str] = None
    staging_relpath: Optional[str] = None
    backup_relpath: Optional[str] = None

    @model_validator(mode="after")
    def _check_action_invariants(self) -> OperationPlanActionV1:
        if not self.path.strip():
            raise SpeakerProfileContractError("plan action path must be non-empty")
        if self.action == "write":
            if self.after_sha256 is None:
                raise SpeakerProfileContractError(
                    "write actions require after_sha256"
                )
            if self.staging_relpath is None:
                raise SpeakerProfileContractError(
                    "write actions require staging_relpath"
                )
        if self.action == "delete":
            if self.after_sha256 is not None:
                raise SpeakerProfileContractError(
                    "delete actions must set after_sha256 to null"
                )
            if self.backup_relpath is None:
                raise SpeakerProfileContractError(
                    "delete actions require backup_relpath"
                )
        return self


class OperationPlanV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions: list[OperationPlanActionV1] = Field(default_factory=list)


class SpeakerProfileOperationV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = SCHEMA_VERSION
    schema_id: Literal["transcriptx.speaker_profile_operation.v1"] = OPERATION_SCHEMA_ID
    operation_id: str
    operation_idempotency_key: str
    op_type: str
    phase: OperationPhase
    plan: OperationPlanV1 = Field(default_factory=OperationPlanV1)
    error_history: list[Any] = Field(default_factory=list)
    receipt: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def _check_operation_invariants(self) -> SpeakerProfileOperationV1:
        if self.schema_id != OPERATION_SCHEMA_ID:
            raise SpeakerProfileContractError(
                f"schema_id must be {OPERATION_SCHEMA_ID!r}"
            )
        if not self.op_type.strip():
            raise SpeakerProfileContractError("op_type must be non-empty")
        if not self.operation_id.strip():
            raise SpeakerProfileContractError("operation_id must be non-empty")
        if not self.operation_idempotency_key.strip():
            raise SpeakerProfileContractError(
                "operation_idempotency_key must be non-empty"
            )
        return self
