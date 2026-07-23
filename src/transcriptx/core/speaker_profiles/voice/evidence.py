"""Canonical voice evidence writers (samples / embeddings) via root journal."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from transcriptx.core.speaker_profiles.hashing import sha256_file
from transcriptx.core.speaker_profiles.layout import link_path, speaker_profiles_project_lock
from transcriptx.core.speaker_profiles.operations import (
    OperationEngine,
    PlannedWrite,
    relative_voice_embedding_path,
    relative_voice_sample_path,
    relative_voice_vector_path,
)
from transcriptx.core.speaker_profiles.provenance import parse_stored_provenance
from transcriptx.core.speaker_profiles.signals import CacheInvalidationSignal
from transcriptx.core.speaker_profiles.store_io import (
    dumps_model,
    ensure_layout,
    read_live_link,
    utc_now_iso,
)
from transcriptx.core.speaker_profiles.voice.activation import ActivationBarrier
from transcriptx.core.speaker_profiles.voice.ids import (
    compute_embedding_id,
    compute_sample_id,
)
from transcriptx.core.speaker_profiles.voice.models import (
    EvidenceTrust,
    VoiceEmbeddingV1,
    VoiceSampleV1,
)
from transcriptx.core.speaker_profiles.voice.vectors import encode_vector_npy_bytes
from transcriptx.core.speaker_profiles.voice.versioning import (
    EMBEDDING_SCHEMA_VERSION,
    PREPROCESSING_POLICY_ID,
    QUALITY_POLICY_ID,
)
from transcriptx.core.utils.file_lock import FileLock
from transcriptx.core.utils.paths import PATHS


def trust_from_link_provenance(provenance: dict[str, Any] | None) -> EvidenceTrust:
    """Map link provenance to evidence trust for enrolment."""
    if not provenance:
        return "manual"
    method = provenance.get("link_method")
    if method == "suggestion_assisted":
        # Incomplete suggestion provenance must not become trusted manual evidence.
        parsed = parse_stored_provenance(provenance)
        if parsed is None:
            return "suggestion_assisted"
        return "suggestion_assisted"
    parsed = parse_stored_provenance(provenance)
    if parsed is None:
        return "manual"
    if parsed.link_method in ("manual", "choose_other", "create_new", "relink"):
        return "manual"
    if parsed.link_method == "suggestion_assisted":
        return "suggestion_assisted"
    return "manual"


def eligibility_for_trust(trust: EvidenceTrust) -> str:
    if trust in ("manual", "promoted"):
        return "eligible"
    if trust == "suggestion_assisted":
        return "ineligible_trust"
    return "ineligible_trust"


@dataclass(frozen=True)
class EnrolExcerptInput:
    clip_start_us: int
    clip_end_us: int
    audio_stat_fingerprint: str
    audio_content_sha256: str
    vector: Any  # np.ndarray
    runtime_metadata: dict[str, Any]
    model_id: str
    model_revision: str
    model_generation_id: str
    eligibility_metrics: dict[str, Any] | None = None


@dataclass(frozen=True)
class EnrolResult:
    sample_ids: tuple[str, ...]
    embedding_ids: tuple[str, ...]
    cache_signal: CacheInvalidationSignal
    replayed: bool = False


class VoiceEvidenceService:
    """Owns canonical voice sample/embedding files under the root journal."""

    def __init__(self, root: Path | None = None, state_dir: Path | None = None) -> None:
        self.root = Path(root) if root is not None else PATHS.speaker_profiles_dir
        self.state_dir = Path(state_dir) if state_dir is not None else PATHS.state_dir
        self.engine = OperationEngine(self.root)
        self.barrier = ActivationBarrier(self.root)

    def _lock(self) -> FileLock:
        return speaker_profiles_project_lock(self.state_dir)

    def enrol_trusted_excerpts_from_link(
        self,
        *,
        operation_idempotency_key: str,
        link_file_key_value: str,
        excerpts: list[EnrolExcerptInput],
        actor: str = "user",
        require_activation: bool = True,
    ) -> EnrolResult:
        """Enrol excerpts for a confirmed live link.

        Only ``manual`` / ``promoted`` trust become eligible references.
        Suggestion-assisted links may store rows as ineligible until promotion.
        Opt-in alone does not call this — bootstrap/UI must invoke explicitly.
        """
        ensure_layout(self.root)
        if require_activation:
            self.barrier.assert_processing_allowed()

        with self._lock():
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                sample_ids = tuple(replay.receipt.get("sample_ids") or ())
                embedding_ids = tuple(replay.receipt.get("embedding_ids") or ())
                return EnrolResult(
                    sample_ids=sample_ids,
                    embedding_ids=embedding_ids,
                    cache_signal=CacheInvalidationSignal(scopes=("speaker_voice",)),
                    replayed=True,
                )

            link = read_live_link(link_file_key_value, root=self.root)
            if link is None:
                from transcriptx.core.speaker_profiles.errors import (
                    SpeakerProfileContractError,
                )

                raise SpeakerProfileContractError("no live link for enrolment")

            trust = trust_from_link_provenance(link.provenance)
            eligibility = eligibility_for_trust(trust)
            link_path_abs = link_path(link_file_key_value, root=self.root)
            link_sha = sha256_file(link_path_abs)
            now = utc_now_iso()

            writes: list[PlannedWrite] = []
            sample_ids: list[str] = []
            embedding_ids: list[str] = []

            for excerpt in excerpts:
                sample_id = compute_sample_id(
                    occurrence_fingerprint=link.occurrence_fingerprint,
                    audio_content_sha256=excerpt.audio_content_sha256,
                    clip_start_us=excerpt.clip_start_us,
                    clip_end_us=excerpt.clip_end_us,
                    model_generation_id=excerpt.model_generation_id,
                )
                embedding_id = compute_embedding_id(
                    sample_id=sample_id,
                    model_generation_id=excerpt.model_generation_id,
                )
                vec_rel = relative_voice_vector_path(embedding_id)
                vector_bytes, meta = encode_vector_npy_bytes(excerpt.vector)

                sample = VoiceSampleV1(
                    sample_id=sample_id,
                    profile_id=link.profile_id,
                    source_link_id=link.link_id,
                    source_link_fingerprint=link.occurrence_fingerprint,
                    source_link_content_sha256=link_sha,
                    managed_transcript_id=link.managed_transcript_id,
                    local_speaker_key=link.local_speaker_key,
                    occurrence_fingerprint=link.occurrence_fingerprint,
                    audio_stat_fingerprint=excerpt.audio_stat_fingerprint,
                    audio_content_sha256=excerpt.audio_content_sha256,
                    clip_start_us=excerpt.clip_start_us,
                    clip_end_us=excerpt.clip_end_us,
                    model_generation_id=excerpt.model_generation_id,
                    preprocessing_policy_id=PREPROCESSING_POLICY_ID,
                    quality_policy_id=QUALITY_POLICY_ID,
                    trust_level=trust,
                    eligibility_state=eligibility,  # type: ignore[arg-type]
                    ownership_provenance={
                        "enrolled_by": actor,
                        "link_method": (link.provenance or {}).get(
                            "link_method", "manual"
                        ),
                    },
                    created_at=now,
                    eligibility_metrics=dict(excerpt.eligibility_metrics or {}),
                )
                embedding = VoiceEmbeddingV1(
                    embedding_id=embedding_id,
                    sample_id=sample_id,
                    profile_id=link.profile_id,
                    source_link_id=link.link_id,
                    source_link_fingerprint=link.occurrence_fingerprint,
                    embedding_schema_version=EMBEDDING_SCHEMA_VERSION,
                    model_id=excerpt.model_id,
                    model_revision=excerpt.model_revision,
                    model_generation_id=excerpt.model_generation_id,
                    preprocessing_policy_id=PREPROCESSING_POLICY_ID,
                    quality_policy_id=QUALITY_POLICY_ID,
                    trust_level=trust,
                    eligibility_state=eligibility,  # type: ignore[arg-type]
                    vector_sha256=str(meta["vector_sha256"]),
                    nbytes=int(meta["nbytes"]),
                    dimension=int(meta["dimension"]),
                    dtype="<f4",
                    runtime_metadata=dict(excerpt.runtime_metadata),
                    created_at=now,
                )
                writes.append(
                    PlannedWrite(
                        relpath=relative_voice_sample_path(sample_id),
                        data=dumps_model(sample),
                    )
                )
                writes.append(
                    PlannedWrite(
                        relpath=relative_voice_embedding_path(embedding_id),
                        data=dumps_model(embedding),
                    )
                )
                writes.append(
                    PlannedWrite(relpath=vec_rel, data=vector_bytes)
                )
                sample_ids.append(sample_id)
                embedding_ids.append(embedding_id)

            event_id = str(uuid4())
            from transcriptx.core.speaker_profiles.models import SpeakerProfileEventV1
            from transcriptx.core.speaker_profiles.operations import relative_event_path

            # No raw scores in Phase 1 events — counts and ids only.
            event = SpeakerProfileEventV1(
                event_id=event_id,
                idempotency_id=event_id,
                operation_idempotency_key=operation_idempotency_key,
                event_type="voice_evidence_enrolled",
                created_at=now,
                actor=actor,
                payload={
                    "profile_id": link.profile_id,
                    "link_id": link.link_id,
                    "sample_ids": sample_ids,
                    "embedding_ids": embedding_ids,
                    "trust_level": trust,
                },
            )
            writes.append(
                PlannedWrite(
                    relpath=relative_event_path(event_id),
                    data=dumps_model(event),
                )
            )

            self.engine.run(
                op_type="voice_enrol_from_link",
                operation_idempotency_key=operation_idempotency_key,
                writes=writes,
                deletes=[],
                receipt_extra={
                    "profile_id": link.profile_id,
                    "link_id": link.link_id,
                    "sample_ids": sample_ids,
                    "embedding_ids": embedding_ids,
                    "event_ids": [event_id],
                    "scopes": ["speaker_voice"],
                },
            )
            return EnrolResult(
                sample_ids=tuple(sample_ids),
                embedding_ids=tuple(embedding_ids),
                cache_signal=CacheInvalidationSignal(
                    scopes=("speaker_voice",),
                    profile_ids=(link.profile_id,),
                    link_ids=(link.link_id,),
                    managed_transcript_ids=(link.managed_transcript_id,),
                ),
                replayed=False,
            )
