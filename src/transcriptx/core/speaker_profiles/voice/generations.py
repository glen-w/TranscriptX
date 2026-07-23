"""Content-addressed model generation pins + active generation pointer."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator

from transcriptx.core.speaker_profiles.errors import SpeakerProfileContractError
from transcriptx.core.speaker_profiles.operations import (
    OperationEngine,
    PlannedWrite,
    relative_voice_active_generation_path,
    relative_voice_generation_path,
)
from transcriptx.core.speaker_profiles.path_safety import assert_safe_relpath
from transcriptx.core.speaker_profiles.store_io import dumps_model, utc_now_iso
from transcriptx.core.speaker_profiles.voice.runtime import (
    EMBEDDING_DIM,
    LOADER_PROFILE_ID,
    MODEL_ID,
    MODEL_REVISION_PIN,
    SPEECHBRAIN_PKG_PIN,
)
from transcriptx.core.speaker_profiles.voice.versioning import (
    ACTIVE_GENERATION_SCHEMA_ID,
    EMBEDDING_SCHEMA_VERSION,
    MODEL_GENERATION_SCHEMA_ID,
    PREPROCESSING_POLICY_ID,
    VOICE_SCHEMA_VERSION,
)

L2_NORM_POLICY_ID = "voice_l2_unit.v1"
TORCH_CONSTRAINT_ID = "torch>=2.6.0"


class VoiceModelGenerationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    version: Literal[1] = VOICE_SCHEMA_VERSION
    schema_id: Literal["voice_model_generation.v1"] = MODEL_GENERATION_SCHEMA_ID  # type: ignore[assignment]
    model_generation_id: str
    model_id: str
    model_revision: str
    speechbrain_pkg: str
    torch_constraint_id: str
    preprocessing_policy_id: str
    embedding_schema_version: str
    l2_norm_policy: str
    loader_profile_id: str
    embedding_dim: int = EMBEDDING_DIM
    created_at: str

    @model_validator(mode="after")
    def _check(self) -> VoiceModelGenerationV1:
        if self.schema_id != MODEL_GENERATION_SCHEMA_ID:
            raise SpeakerProfileContractError("invalid model generation schema_id")
        expected = compute_model_generation_id(
            model_id=self.model_id,
            model_revision=self.model_revision,
            speechbrain_pkg=self.speechbrain_pkg,
            torch_constraint_id=self.torch_constraint_id,
            preprocessing_policy_id=self.preprocessing_policy_id,
            embedding_schema_version=self.embedding_schema_version,
            l2_norm_policy=self.l2_norm_policy,
        )
        if self.model_generation_id != expected:
            raise SpeakerProfileContractError(
                "model_generation_id must equal content-addressed hash of pin fields"
            )
        return self


class VoiceActiveGenerationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    version: Literal[1] = VOICE_SCHEMA_VERSION
    schema_id: Literal["voice_active_generation.v1"] = ACTIVE_GENERATION_SCHEMA_ID  # type: ignore[assignment]
    model_generation_id: str
    activated_at: str


def compute_model_generation_id(
    *,
    model_id: str,
    model_revision: str,
    speechbrain_pkg: str,
    torch_constraint_id: str,
    preprocessing_policy_id: str,
    embedding_schema_version: str,
    l2_norm_policy: str,
) -> str:
    payload = json.dumps(
        [
            "voice_model_generation_id.v1",
            model_id,
            model_revision,
            speechbrain_pkg,
            torch_constraint_id,
            preprocessing_policy_id,
            embedding_schema_version,
            l2_norm_policy,
        ],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def default_generation_pin(*, created_at: str | None = None) -> VoiceModelGenerationV1:
    mid = compute_model_generation_id(
        model_id=MODEL_ID,
        model_revision=MODEL_REVISION_PIN,
        speechbrain_pkg=SPEECHBRAIN_PKG_PIN,
        torch_constraint_id=TORCH_CONSTRAINT_ID,
        preprocessing_policy_id=PREPROCESSING_POLICY_ID,
        embedding_schema_version=EMBEDDING_SCHEMA_VERSION,
        l2_norm_policy=L2_NORM_POLICY_ID,
    )
    return VoiceModelGenerationV1(
        model_generation_id=mid,
        model_id=MODEL_ID,
        model_revision=MODEL_REVISION_PIN,
        speechbrain_pkg=SPEECHBRAIN_PKG_PIN,
        torch_constraint_id=TORCH_CONSTRAINT_ID,
        preprocessing_policy_id=PREPROCESSING_POLICY_ID,
        embedding_schema_version=EMBEDDING_SCHEMA_VERSION,
        l2_norm_policy=L2_NORM_POLICY_ID,
        loader_profile_id=LOADER_PROFILE_ID,
        embedding_dim=EMBEDDING_DIM,
        created_at=created_at or utc_now_iso(),
    )


class VoiceGenerationRegistry:
    """Write-once generation pins + journalled active pointer."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.engine = OperationEngine(self.root)

    def read_generation(self, model_generation_id: str) -> Optional[VoiceModelGenerationV1]:
        rel = relative_voice_generation_path(model_generation_id)
        assert_safe_relpath(rel)
        path = self.root / rel
        if not path.is_file():
            return None
        return VoiceModelGenerationV1.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def read_active(self) -> Optional[VoiceActiveGenerationV1]:
        rel = relative_voice_active_generation_path()
        path = self.root / rel
        if not path.is_file():
            return None
        return VoiceActiveGenerationV1.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def ensure_default_generation_and_activate(
        self, *, operation_idempotency_key: str
    ) -> VoiceModelGenerationV1:
        """Idempotently write default pin (write-once) and set active pointer."""
        pin = default_generation_pin()
        replay = self.engine.find_complete(operation_idempotency_key)
        if replay is not None:
            existing = self.read_generation(pin.model_generation_id)
            if existing is not None:
                return existing
            return pin

        writes: list[PlannedWrite] = []
        gen_rel = relative_voice_generation_path(pin.model_generation_id)
        gen_path = self.root / gen_rel
        if not gen_path.exists():
            writes.append(PlannedWrite(relpath=gen_rel, data=dumps_model(pin)))
        else:
            # Write-once: existing file must match
            existing = self.read_generation(pin.model_generation_id)
            if existing is None or existing.model_generation_id != pin.model_generation_id:
                raise SpeakerProfileContractError(
                    "generation pin collision or corrupt generation file"
                )

        active = VoiceActiveGenerationV1(
            model_generation_id=pin.model_generation_id,
            activated_at=utc_now_iso(),
        )
        writes.append(
            PlannedWrite(
                relpath=relative_voice_active_generation_path(),
                data=dumps_model(active),
            )
        )
        if writes:
            self.engine.run(
                op_type="voice_activate_generation",
                operation_idempotency_key=operation_idempotency_key,
                writes=writes,
                deletes=[],
                receipt_extra={
                    "model_generation_id": pin.model_generation_id,
                    "scopes": ["speaker_voice"],
                },
            )
        return pin
