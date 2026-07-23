"""Journalled promotion of suggestion_assisted evidence to trusted."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from transcriptx.core.speaker_profiles.errors import SpeakerProfileContractError
from transcriptx.core.speaker_profiles.layout import speaker_profiles_project_lock
from transcriptx.core.speaker_profiles.operations import (
    OperationEngine,
    PlannedWrite,
    relative_event_path,
    relative_voice_decision_path,
    relative_voice_embedding_path,
    relative_voice_sample_path,
)
from transcriptx.core.speaker_profiles.store_io import dumps_model, ensure_layout, utc_now_iso
from transcriptx.core.speaker_profiles.voice.activation import ActivationBarrier
from transcriptx.core.speaker_profiles.voice.models import (
    VoiceEmbeddingV1,
    VoiceMatchDecisionV1,
    VoiceSampleV1,
)
from transcriptx.core.utils.paths import PATHS


class VoicePromotionService:
    def __init__(self, root: Path | None = None, state_dir: Path | None = None) -> None:
        self.root = Path(root) if root is not None else PATHS.speaker_profiles_dir
        self.state_dir = Path(state_dir) if state_dir is not None else PATHS.state_dir
        self.engine = OperationEngine(self.root)
        self.barrier = ActivationBarrier(self.root)

    def promote_sample(
        self,
        *,
        operation_idempotency_key: str,
        sample_id: str,
        actor: str = "user",
        require_activation: bool = True,
    ) -> str:
        """Promote one sample (+ sibling embedding) to trust=promoted / eligible."""
        if require_activation:
            self.barrier.assert_processing_allowed()
        ensure_layout(self.root)
        with speaker_profiles_project_lock(self.state_dir):
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                return str(replay.receipt.get("decision_id") or "")

            sample_path = self.root / relative_voice_sample_path(sample_id)
            if not sample_path.is_file():
                raise SpeakerProfileContractError(f"sample not found: {sample_id}")
            sample = VoiceSampleV1.model_validate_json(
                sample_path.read_text(encoding="utf-8")
            )
            if sample.trust_level == "promoted" and sample.eligibility_state == "eligible":
                return ""

            now = utc_now_iso()
            new_sample = sample.model_copy(
                update={
                    "trust_level": "promoted",
                    "eligibility_state": "eligible",
                }
            )
            writes = [
                PlannedWrite(
                    relpath=relative_voice_sample_path(sample_id),
                    data=dumps_model(new_sample),
                )
            ]
            emb_dir = self.root / "voice" / "embeddings"
            if emb_dir.is_dir():
                for path in emb_dir.glob("*.voice_embedding.json"):
                    try:
                        emb = VoiceEmbeddingV1.model_validate_json(
                            path.read_text(encoding="utf-8")
                        )
                    except Exception:
                        continue
                    if emb.sample_id != sample_id:
                        continue
                    new_emb = emb.model_copy(
                        update={
                            "trust_level": "promoted",
                            "eligibility_state": "eligible",
                        }
                    )
                    writes.append(
                        PlannedWrite(
                            relpath=relative_voice_embedding_path(emb.embedding_id),
                            data=dumps_model(new_emb),
                        )
                    )

            decision_id = str(uuid4())
            decision = VoiceMatchDecisionV1(
                decision_id=decision_id,
                decision_kind="promote",
                scope="occurrence_profile",
                managed_transcript_id=sample.managed_transcript_id,
                local_speaker_key=sample.local_speaker_key,
                occurrence_fingerprint=sample.occurrence_fingerprint,
                candidate_profile_id=sample.profile_id,
                created_at=now,
                actor=actor,
            )
            writes.append(
                PlannedWrite(
                    relpath=relative_voice_decision_path(decision_id),
                    data=dumps_model(decision),
                )
            )
            event_id = str(uuid4())
            from transcriptx.core.speaker_profiles.models import SpeakerProfileEventV1

            event = SpeakerProfileEventV1(
                event_id=event_id,
                idempotency_id=event_id,
                operation_idempotency_key=operation_idempotency_key,
                event_type="voice_evidence_promoted",
                created_at=now,
                actor=actor,
                payload={
                    "sample_id": sample_id,
                    "profile_id": sample.profile_id,
                    "decision_id": decision_id,
                },
            )
            writes.append(
                PlannedWrite(
                    relpath=relative_event_path(event_id),
                    data=dumps_model(event),
                )
            )
            self.engine.run(
                op_type="voice_promote_sample",
                operation_idempotency_key=operation_idempotency_key,
                writes=writes,
                deletes=[],
                receipt_extra={
                    "decision_id": decision_id,
                    "sample_id": sample_id,
                    "scopes": ["speaker_voice"],
                },
            )
            return decision_id
