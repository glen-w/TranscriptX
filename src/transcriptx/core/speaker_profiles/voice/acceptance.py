"""Cross-domain voice acceptance owner (link + decision).

Reject is a single root journal. Accept journals the link mutation, the
accept decision, and retained query-evidence enrolment in one
``OperationEngine.run`` via ``extra_writes`` / ``extra_writes_builder`` on
the Phase 1 link APIs (avatar co-journal precedent).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from transcriptx.core.speaker_profiles.errors import (
    SpeakerProfileContractError,
    StaleConfirmationError,
)
from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.operations import (
    OperationEngine,
    PlannedWrite,
    relative_voice_decision_path,
)
from transcriptx.core.speaker_profiles.provenance import LinkProvenanceV1
from transcriptx.core.speaker_profiles.service import (
    LinkMutationContext,
    MutationResult,
    SpeakerProfileService,
)
from transcriptx.core.speaker_profiles.signals import CacheInvalidationSignal
from transcriptx.core.speaker_profiles.store_io import (
    dumps_model,
    ensure_layout,
    read_live_link,
    read_profile,
    utc_now_iso,
)
from transcriptx.core.speaker_profiles.voice.activation import ActivationBarrier
from transcriptx.core.speaker_profiles.voice.caches import VoiceQueryCache
from transcriptx.core.speaker_profiles.voice.evidence import (
    EnrolExcerptInput,
    plan_enrol_excerpt_writes,
)
from transcriptx.core.speaker_profiles.voice.models import VoiceMatchDecisionV1
from transcriptx.core.speaker_profiles.voice.runtime import MODEL_ID, MODEL_REVISION_PIN
from transcriptx.core.utils.paths import PATHS


@dataclass(frozen=True)
class AcceptSuggestionRequest:
    operation_idempotency_key: str
    managed_transcript_id: str
    local_speaker_key: str
    candidate_profile_id: str
    suggestion_id: str
    suggestion_digest: str
    confidence_category: str
    model_generation_id: str
    occurrence_fingerprint: str
    expected_link_id: str | None = None
    expected_owner_profile_id: str | None = None
    expected_fingerprint: str | None = None
    expected_audio_stat_fingerprint: str | None = None
    expected_audio_content_sha256: str | None = None
    expected_suggestion_digest: str | None = None
    create_new_profile: bool = False
    display_name: str | None = None
    actor: str = "user"
    query_cache_key: str | None = None
    query_excerpts: tuple[EnrolExcerptInput, ...] = ()


@dataclass(frozen=True)
class AcceptanceResult:
    mutation: MutationResult | None
    decision_id: str | None
    cache_signal: CacheInvalidationSignal
    sample_ids: tuple[str, ...] = ()
    embedding_ids: tuple[str, ...] = ()


class VoiceAcceptanceOwner:
    """Sole entry for confirming / rejecting voice suggestions."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        state_dir: Path | None = None,
        profile_service: SpeakerProfileService | None = None,
    ) -> None:
        self.root = Path(root) if root is not None else PATHS.speaker_profiles_dir
        self.state_dir = Path(state_dir) if state_dir is not None else PATHS.state_dir
        self.profiles = profile_service or SpeakerProfileService(
            root=self.root, state_dir=self.state_dir
        )
        self.barrier = ActivationBarrier(self.root)
        self.engine = OperationEngine(self.root)
        self.query_cache = VoiceQueryCache(self.root)

    def _assert_accept_preconditions(self, request: AcceptSuggestionRequest) -> None:
        """Fail closed on stale link/owner/fingerprint/profile/suggestion digest."""
        digest = request.expected_suggestion_digest or request.suggestion_digest
        if digest != request.suggestion_digest:
            raise StaleConfirmationError("suggestion digest mismatch")

        profile = read_profile(request.candidate_profile_id, root=self.root)
        if profile is None:
            raise SpeakerProfileContractError(
                f"profile not found: {request.candidate_profile_id}"
            )
        if profile.status != "active":
            raise StaleConfirmationError(
                f"expected active profile, found status {profile.status!r}"
            )

        if (
            request.expected_audio_stat_fingerprint is not None
            or request.expected_audio_content_sha256 is not None
        ):
            from transcriptx.core.speaker_profiles.resolver import (
                ManagedTranscriptResolver,
            )
            from transcriptx.core.speaker_profiles.voice.audio_resolve import (
                resolve_managed_transcript_audio,
            )

            try:
                resolved = ManagedTranscriptResolver().resolve(
                    request.managed_transcript_id
                )
                audio = resolve_managed_transcript_audio(Path(resolved.transcript_path))
            except Exception as exc:
                raise StaleConfirmationError(
                    f"audio identity unavailable: {exc}"
                ) from exc
            if (
                request.expected_audio_stat_fingerprint is not None
                and audio.audio_stat_fingerprint
                != request.expected_audio_stat_fingerprint
            ):
                raise StaleConfirmationError("expected_audio_stat_fingerprint mismatch")
            if (
                request.expected_audio_content_sha256 is not None
                and audio.audio_content_sha256 != request.expected_audio_content_sha256
            ):
                raise StaleConfirmationError("expected_audio_content_sha256 mismatch")

        key = link_file_key(request.managed_transcript_id, request.local_speaker_key)
        existing = read_live_link(key, root=self.root)

        if request.create_new_profile:
            if existing is not None:
                raise StaleConfirmationError(
                    "occurrence already linked; cannot create_new_profile"
                )
            return

        if existing is None:
            if request.expected_link_id is not None:
                raise StaleConfirmationError("expected live link missing")
            return

        if (
            request.expected_link_id is not None
            and existing.link_id != request.expected_link_id
        ):
            raise StaleConfirmationError("expected_link_id mismatch")
        if (
            request.expected_owner_profile_id is not None
            and existing.profile_id != request.expected_owner_profile_id
        ):
            raise StaleConfirmationError("expected_owner_profile_id mismatch")
        if (
            request.expected_fingerprint is not None
            and existing.occurrence_fingerprint != request.expected_fingerprint
        ):
            raise StaleConfirmationError("expected_fingerprint mismatch")
        if (
            request.occurrence_fingerprint
            and existing.occurrence_fingerprint != request.occurrence_fingerprint
            and request.expected_fingerprint is None
        ):
            raise StaleConfirmationError(
                "occurrence fingerprint drift; pass expected_fingerprint for supersede"
            )

    def _resolve_query_excerpts(
        self, request: AcceptSuggestionRequest
    ) -> list[EnrolExcerptInput]:
        if request.query_excerpts:
            return list(request.query_excerpts)
        if not request.query_cache_key:
            return []
        cached = self.query_cache.read(request.query_cache_key)
        if cached is None:
            return []
        meta, vectors = cached
        ranges = list(meta.get("ranges_us") or [])
        if len(ranges) != len(vectors):
            return []
        model_id = str(meta.get("model_id") or MODEL_ID)
        model_revision = str(meta.get("model_revision") or MODEL_REVISION_PIN)
        model_generation_id = str(
            meta.get("model_generation_id") or request.model_generation_id
        )
        audio_stat = str(
            meta.get("audio_stat_fingerprint")
            or request.expected_audio_stat_fingerprint
            or ""
        )
        audio_sha = str(
            meta.get("audio_content_sha256")
            or request.expected_audio_content_sha256
            or ""
        )
        if not audio_stat or not audio_sha:
            return []
        excerpts: list[EnrolExcerptInput] = []
        for (start_us, end_us), vector in zip(ranges, vectors, strict=True):
            excerpts.append(
                EnrolExcerptInput(
                    clip_start_us=int(start_us),
                    clip_end_us=int(end_us),
                    audio_stat_fingerprint=audio_stat,
                    audio_content_sha256=audio_sha,
                    vector=vector,
                    runtime_metadata={
                        "source": "accept_query_cache",
                        "query_cache_key": request.query_cache_key,
                    },
                    model_id=model_id,
                    model_revision=model_revision,
                    model_generation_id=model_generation_id,
                )
            )
        return excerpts

    def _decision_write(
        self, request: AcceptSuggestionRequest, decision_id: str
    ) -> PlannedWrite:
        decision = VoiceMatchDecisionV1(
            decision_id=decision_id,
            decision_kind="accept",
            scope="occurrence_profile",
            managed_transcript_id=request.managed_transcript_id,
            local_speaker_key=request.local_speaker_key,
            occurrence_fingerprint=request.occurrence_fingerprint,
            candidate_profile_id=request.candidate_profile_id,
            suggestion_id=request.suggestion_id,
            suggestion_digest=request.suggestion_digest,
            model_generation_id=request.model_generation_id,
            confidence_category=request.confidence_category,
            created_at=utc_now_iso(),
            actor=request.actor,
        )
        return PlannedWrite(
            relpath=relative_voice_decision_path(decision_id),
            data=dumps_model(decision),
        )

    def reject_suggestion(
        self,
        *,
        operation_idempotency_key: str,
        managed_transcript_id: str,
        local_speaker_key: str,
        occurrence_fingerprint: str,
        candidate_profile_id: str,
        suggestion_id: str,
        suggestion_digest: str,
        model_generation_id: str,
        reference_corpus_digest: str,
        reference_count: int,
        actor: str = "user",
        require_activation: bool = True,
    ) -> AcceptanceResult:
        if require_activation:
            self.barrier.assert_processing_allowed()
        ensure_layout(self.root)
        decision_id = str(uuid4())
        now = utc_now_iso()
        decision = VoiceMatchDecisionV1(
            decision_id=decision_id,
            decision_kind="reject",
            scope="occurrence_profile",
            managed_transcript_id=managed_transcript_id,
            local_speaker_key=local_speaker_key,
            occurrence_fingerprint=occurrence_fingerprint,
            candidate_profile_id=candidate_profile_id,
            suggestion_id=suggestion_id,
            suggestion_digest=suggestion_digest,
            model_generation_id=model_generation_id,
            reference_count_at_decision=reference_count,
            reference_corpus_digest=reference_corpus_digest,
            created_at=now,
            actor=actor,
        )
        self.engine.run(
            op_type="voice_reject_suggestion",
            operation_idempotency_key=operation_idempotency_key,
            writes=[
                PlannedWrite(
                    relpath=relative_voice_decision_path(decision_id),
                    data=dumps_model(decision),
                )
            ],
            deletes=[],
            receipt_extra={
                "decision_id": decision_id,
                "scopes": ["speaker_voice"],
            },
        )
        return AcceptanceResult(
            mutation=None,
            decision_id=decision_id,
            cache_signal=CacheInvalidationSignal(scopes=("speaker_voice",)),
        )

    def leave_unlinked(self) -> AcceptanceResult:
        """Session-only — must not write a durable rejection."""
        return AcceptanceResult(
            mutation=None,
            decision_id=None,
            cache_signal=CacheInvalidationSignal(scopes=("speaker_voice",)),
        )

    def accept_suggestion(
        self,
        request: AcceptSuggestionRequest,
        *,
        require_activation: bool = True,
    ) -> AcceptanceResult:
        if require_activation:
            self.barrier.assert_processing_allowed()
        ensure_layout(self.root)

        replay = self.engine.find_complete(request.operation_idempotency_key)
        if replay is not None:
            return AcceptanceResult(
                mutation=self.profiles._result_from_receipt(replay),  # noqa: SLF001
                decision_id=str(replay.receipt.get("decision_id") or "") or None,
                cache_signal=CacheInvalidationSignal(
                    scopes=("speaker_profiles", "speaker_links", "speaker_voice"),
                ),
                sample_ids=tuple(replay.receipt.get("sample_ids") or ()),
                embedding_ids=tuple(replay.receipt.get("embedding_ids") or ()),
            )

        self._assert_accept_preconditions(request)
        excerpts = self._resolve_query_excerpts(request)

        decision_id = str(uuid4())
        decision_write = self._decision_write(request, decision_id)
        sample_ids: list[str] = []
        embedding_ids: list[str] = []

        def _builder(ctx: LinkMutationContext) -> list[PlannedWrite]:
            if not excerpts:
                return []
            planned = plan_enrol_excerpt_writes(
                profile_id=ctx.profile_id,
                link_id=ctx.link_id,
                source_link_content_sha256=ctx.link_content_sha256,
                managed_transcript_id=ctx.managed_transcript_id,
                local_speaker_key=ctx.local_speaker_key,
                occurrence_fingerprint=ctx.occurrence_fingerprint,
                excerpts=excerpts,
                operation_idempotency_key=request.operation_idempotency_key,
                trust="suggestion_assisted",
                actor=request.actor,
            )
            # Mutate in place so extra_receipt lists (same objects) stay current.
            sample_ids.clear()
            sample_ids.extend(planned.sample_ids)
            embedding_ids.clear()
            embedding_ids.extend(planned.embedding_ids)
            return list(planned.writes)

        extra_kw = {
            "extra_writes": [decision_write],
            "extra_writes_builder": _builder if excerpts else None,
            "extra_scopes": ["speaker_voice"],
            "extra_receipt": {
                "decision_id": decision_id,
                "sample_ids": sample_ids,
                "embedding_ids": embedding_ids,
            },
        }

        provenance = LinkProvenanceV1(
            link_method="suggestion_assisted",
            suggestion_id=request.suggestion_id,
            suggestion_digest=request.suggestion_digest,
            model_generation_id=request.model_generation_id,
            confidence_category=request.confidence_category,  # type: ignore[arg-type]
            voice_acceptance_op_id=request.operation_idempotency_key,
            decision_id=decision_id,
        )

        if request.create_new_profile:
            if not request.display_name:
                raise SpeakerProfileContractError(
                    "display_name required when create_new_profile"
                )
            mutation = self.profiles.create_profile_and_link(
                operation_idempotency_key=request.operation_idempotency_key,
                display_name=request.display_name,
                managed_transcript_id=request.managed_transcript_id,
                local_speaker_key=request.local_speaker_key,
                created_by=request.actor,
                provenance=LinkProvenanceV1(
                    link_method="create_new",
                    voice_acceptance_op_id=request.operation_idempotency_key,
                    decision_id=decision_id,
                ),
                **extra_kw,
            )
        elif request.expected_link_id and request.expected_owner_profile_id:
            if request.expected_owner_profile_id == request.candidate_profile_id:
                mutation = self.profiles.supersede_link_fingerprint(
                    operation_idempotency_key=request.operation_idempotency_key,
                    managed_transcript_id=request.managed_transcript_id,
                    local_speaker_key=request.local_speaker_key,
                    expected_link_id=request.expected_link_id,
                    expected_fingerprint=request.expected_fingerprint,
                    actor=request.actor,
                    provenance=provenance,
                    **extra_kw,
                )
            else:
                mutation = self.profiles.relink(
                    operation_idempotency_key=request.operation_idempotency_key,
                    managed_transcript_id=request.managed_transcript_id,
                    local_speaker_key=request.local_speaker_key,
                    profile_id=request.candidate_profile_id,
                    expected_link_id=request.expected_link_id,
                    expected_owner_profile_id=request.expected_owner_profile_id,
                    actor=request.actor,
                    provenance=provenance,
                    **extra_kw,
                )
        else:
            mutation = self.profiles.link_existing_profile(
                operation_idempotency_key=request.operation_idempotency_key,
                managed_transcript_id=request.managed_transcript_id,
                local_speaker_key=request.local_speaker_key,
                profile_id=request.candidate_profile_id,
                actor=request.actor,
                provenance=provenance,
                **extra_kw,
            )

        # Builder mutates sample_ids during the journal; refresh receipt fields.
        receipt_sample_ids = tuple(
            mutation.outcome.receipt.get("sample_ids") or sample_ids
        )
        receipt_embedding_ids = tuple(
            mutation.outcome.receipt.get("embedding_ids") or embedding_ids
        )
        scopes = ("speaker_profiles", "speaker_links", "speaker_voice")
        return AcceptanceResult(
            mutation=mutation,
            decision_id=decision_id,
            cache_signal=CacheInvalidationSignal(
                scopes=scopes,
                profile_ids=mutation.cache_signal.profile_ids,
                link_ids=mutation.cache_signal.link_ids,
                managed_transcript_ids=mutation.cache_signal.managed_transcript_ids,
            ),
            sample_ids=tuple(receipt_sample_ids),
            embedding_ids=tuple(receipt_embedding_ids),
        )
