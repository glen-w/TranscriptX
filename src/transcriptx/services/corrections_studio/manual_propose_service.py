"""Manual propose API for Corrections Studio / Transcript viewer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha1
from typing import List, Optional, Tuple

from transcriptx.core.corrections.detect import resolve_segment_id
from transcriptx.core.store.corrections_session_store import GenerationCommitConflict
from transcriptx.core.utils.canonicalization import compute_transcript_identity_hash
from transcriptx.io import load_segments
from transcriptx.services.corrections_studio.generation_manifest import (
    STUDIO_DETECTOR_VERSION,
    GenerationManifest,
    studio_session_rules_fingerprint,
)
from transcriptx.services.corrections_studio.identity import (
    compute_generation_manifest_hash,
)
from transcriptx.services.corrections_studio.occurrence_keys import (
    stable_occurrence_key,
)
from transcriptx.services.corrections_studio.schema import (
    ApplyScope,
    CandidateEvidence,
    CandidateSource,
    EvidenceSignal,
    EvidenceStrength,
    GenerationOrigin,
    LearnIntent,
    ManualProposedPayload,
    ManualSeedGenerationPayload,
    ReviewAction,
    ReviewRecordedPayload,
    ReviewStatus,
    StudioCandidate,
    StudioEventEnvelope,
    StudioGenerationRecord,
    StudioOccurrence,
    StudioReviewRecord,
    StudioSessionDocument,
)
from transcriptx.services.corrections_studio.semantic_identity import (
    compute_manual_semantic_identity_key,
)
from transcriptx.services.corrections_studio.session_service import (
    CorrectionsStudioSessionService,
    PersistPreconditions,
)


class ManualProposeConflict(ValueError):
    """Different replacement already proposed for the same span."""

    def __init__(self, message: str, *, existing_candidate_id: str):
        super().__init__(message)
        self.existing_candidate_id = existing_candidate_id


class ManualProposeValidationError(ValueError):
    """Fresh transcript revalidation failed for a manual propose."""


@dataclass(frozen=True)
class ManualProposeResult:
    session: StudioSessionDocument
    candidate: StudioCandidate
    upserted: bool
    auto_accepted: bool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _manual_candidate_id(wrong: str, right: str, occ_key: str) -> str:
    return sha1(f"manual:{wrong}:{right}:{occ_key}".encode("utf-8")).hexdigest()


def _snippet_for(text: str, start: int, end: int, pad: int = 24) -> str:
    lo = max(0, start - pad)
    hi = min(len(text), end + pad)
    return text[lo:hi]


def _find_segment(
    segments: list,
    *,
    transcript_key: str,
    segment_id: Optional[str],
    segment_index: Optional[int],
) -> Tuple[int, dict, str]:
    if segment_index is not None:
        if segment_index < 0 or segment_index >= len(segments):
            raise ManualProposeValidationError(
                f"segment_index {segment_index} out of range"
            )
        seg = segments[segment_index]
        if not isinstance(seg, dict):
            raise ManualProposeValidationError("segment is not an object")
        sid = resolve_segment_id(seg, transcript_key, segment_index=segment_index)
        if segment_id is not None and segment_id != sid:
            raise ManualProposeValidationError(
                f"segment_id mismatch: expected {segment_id!r}, got {sid!r}"
            )
        return segment_index, seg, sid

    if not segment_id:
        raise ManualProposeValidationError("segment_id or segment_index is required")
    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            continue
        sid = resolve_segment_id(seg, transcript_key, segment_index=i)
        if sid == segment_id:
            return i, seg, sid
    raise ManualProposeValidationError(f"segment_id not found: {segment_id}")


def _span_key(segment_id: str, span: Tuple[int, int]) -> str:
    return f"{segment_id}:{span[0]}:{span[1]}"


def _empty_manual_manifest(transcript_identity_hash: str) -> GenerationManifest:
    return GenerationManifest(
        transcript_identity_hash=transcript_identity_hash,
        corrections_config_fingerprint="",
        detector_version=STUDIO_DETECTOR_VERSION,
        memory_rule_fingerprint="",
        speaker_map_fingerprint="",
        studio_session_rules_fingerprint="",
        llm_fingerprint="",
        llm_prompt_version="",
        llm_schema_version="",
        context_pack_version="manual_seed",
    )


class CorrectionsStudioManualProposeService:
    def __init__(self, session_service: CorrectionsStudioSessionService) -> None:
        self._session = session_service

    def propose_manual_correction(
        self,
        session_id: str,
        *,
        segment_id: Optional[str] = None,
        segment_index: Optional[int] = None,
        span: Tuple[int, int],
        wrong_text: str,
        right_text: str,
        auto_accept: bool = False,
        supersede_existing: bool = False,
    ) -> ManualProposeResult:
        doc = self._session.load_document(session_id)
        transcript_path = doc.transcript_path
        segments = load_segments(transcript_path)
        live_identity = compute_transcript_identity_hash(segments)
        if live_identity != doc.recorded_transcript_identity_hash:
            raise ManualProposeValidationError(
                "Transcript identity changed; refresh the session before proposing"
            )

        if not wrong_text:
            raise ManualProposeValidationError("wrong_text must be non-empty")
        if not right_text:
            raise ManualProposeValidationError("right_text must be non-empty")
        if wrong_text == right_text:
            raise ManualProposeValidationError("replacement is a no-op")

        start, end = int(span[0]), int(span[1])
        if start < 0 or end <= start:
            raise ManualProposeValidationError("invalid char span")

        idx, seg, sid = _find_segment(
            segments,
            transcript_key=live_identity,
            segment_id=segment_id,
            segment_index=segment_index,
        )
        text = seg.get("text") or ""
        if not isinstance(text, str):
            text = str(text)
        if end > len(text):
            raise ManualProposeValidationError("span exceeds segment text length")
        if text[start:end] != wrong_text:
            raise ManualProposeValidationError(
                "wrong_text does not match segment text at span"
            )

        occ_key = stable_occurrence_key(sid, start, end, wrong_text)
        sem_key = compute_manual_semantic_identity_key(wrong_text, right_text)
        span_identity = _span_key(sid, (start, end))

        gen_id = doc.current_generation_id
        current_cands = [
            c
            for c in doc.candidates
            if gen_id is not None and c.generation_id == gen_id
        ]

        # Duplicate semantics (H7)
        existing_same: Optional[StudioCandidate] = None
        conflicting: Optional[StudioCandidate] = None
        for c in current_cands:
            if not (
                c.kind == "manual" or CandidateSource.viewer_manual in (c.sources or [])
            ):
                continue
            for occ in c.occurrences:
                if occ.segment_id != sid or occ.span is None:
                    continue
                if tuple(occ.span) != (start, end):
                    continue
                if c.wrong_text == wrong_text and c.right_text == right_text:
                    existing_same = c
                elif c.wrong_text == wrong_text and c.right_text != right_text:
                    conflicting = c
                elif span_identity == _span_key(sid, tuple(occ.span)):
                    if c.right_text != right_text:
                        conflicting = c

        if conflicting is not None and not supersede_existing:
            raise ManualProposeConflict(
                "A different replacement is already proposed for this span; "
                "pass supersede_existing=True to replace it",
                existing_candidate_id=conflicting.candidate_id,
            )

        expected_last = self._session.last_event_sequence(session_id)
        expected_gen = doc.current_generation_id
        expected_identity = doc.recorded_transcript_identity_hash
        expected_rules_fp = studio_session_rules_fingerprint(doc.rules)
        now = _now()

        occ = StudioOccurrence(
            segment_id=sid,
            stable_occurrence_key=occ_key,
            span=(start, end),
            snippet=_snippet_for(text, start, end),
            speaker=seg.get("speaker") if isinstance(seg.get("speaker"), str) else None,
            time_start=seg.get("start", seg.get("start_time")),
            time_end=seg.get("end", seg.get("end_time")),
            segment_index=idx,
        )

        events: List[StudioEventEnvelope] = []
        new_gen_created = False

        if gen_id is None:
            gen_id = 1
            new_gen_created = True
            manifest = _empty_manual_manifest(live_identity)
            mh = compute_generation_manifest_hash(manifest)
            seed_payload = ManualSeedGenerationPayload(
                generation_id=gen_id,
                generation_origin=GenerationOrigin.manual_seed,
                transcript_identity_hash=live_identity,
            )
            events.append(
                StudioEventEnvelope(
                    session_id=session_id,
                    event_type="manual_seed_generation",
                    event_sequence=0,
                    generation_id=gen_id,
                    payload=seed_payload.model_dump(mode="json"),
                    payload_schema_version=2,
                    timestamp=now,
                )
            )
            doc = doc.model_copy(
                update={
                    "current_generation_id": gen_id,
                    "current_generation": StudioGenerationRecord(
                        generation_id=gen_id,
                        generation_manifest=manifest,
                        generation_manifest_hash=mh,
                        candidate_ids=[],
                        completed_at=now,
                        generation_diagnostics=None,
                        generation_origin=GenerationOrigin.manual_seed,
                    ),
                    "candidates": [],
                }
            )

        upserted = False
        superseded_id: Optional[str] = None
        if existing_same is not None:
            # Merge/upsert occurrence onto existing candidate
            occ_keys = {o.stable_occurrence_key for o in existing_same.occurrences}
            if occ_key in occ_keys:
                merged_occs = list(existing_same.occurrences)
            else:
                merged_occs = list(existing_same.occurrences) + [occ]
            cand = existing_same.model_copy(
                update={
                    "occurrences": merged_occs,
                    "generation_id": gen_id,
                }
            )
            upserted = True
        else:
            status = ReviewStatus.accepted if auto_accept else ReviewStatus.pending
            cand = StudioCandidate(
                candidate_id=_manual_candidate_id(wrong_text, right_text, occ_key),
                generation_id=gen_id,
                kind="manual",
                wrong_text=wrong_text,
                right_text=right_text,
                confidence=1.0,
                rule_id=None,
                occurrences=[occ],
                review_status=status,
                sources=[CandidateSource.viewer_manual],
                evidence=CandidateEvidence(
                    strength=EvidenceStrength.strong,
                    signals=[EvidenceSignal.viewer_edit],
                    rationale="viewer_manual",
                    review_priority="high",
                ),
                semantic_identity_key=sem_key,
            )
            if conflicting is not None and supersede_existing:
                superseded_id = conflicting.candidate_id

        historical = [c for c in doc.candidates if c.generation_id != gen_id]
        current_others = [
            c
            for c in doc.candidates
            if c.generation_id == gen_id
            and c.candidate_id != cand.candidate_id
            and c.candidate_id != (superseded_id or "")
        ]
        new_candidates = historical + current_others + [cand]

        review_records = list(doc.review_records)
        if auto_accept:
            # Drop prior current-gen review for this candidate, append accept
            review_records = [
                r
                for r in review_records
                if not (
                    r.candidate_id == cand.candidate_id and r.generation_id == gen_id
                )
            ]
            review_records.append(
                StudioReviewRecord(
                    session_id=session_id,
                    generation_id=gen_id,
                    candidate_id=cand.candidate_id,
                    review_action=ReviewAction.accept,
                    apply_scope=ApplyScope.all,
                    selected_occurrence_keys=[],
                    learn_intent=LearnIntent.none,
                    review_target_text=right_text,
                    recorded_at=now,
                    event_sequence=0,
                )
            )
            cand = cand.model_copy(update={"review_status": ReviewStatus.accepted})
            # Replace cand in new_candidates
            new_candidates = [
                (
                    cand
                    if c.candidate_id == cand.candidate_id and c.generation_id == gen_id
                    else c
                )
                for c in new_candidates
            ]

        gen_rec = doc.current_generation
        if gen_rec is None:
            raise RuntimeError("generation missing after seed")
        updated_gen = gen_rec.model_copy(
            update={
                "candidate_ids": [
                    c.candidate_id for c in new_candidates if c.generation_id == gen_id
                ],
                "completed_at": now if new_gen_created else gen_rec.completed_at,
            }
        )

        doc = doc.model_copy(
            update={
                "current_generation_id": gen_id,
                "current_generation": updated_gen,
                "candidates": new_candidates,
                "review_records": review_records,
                "updated_at": now,
            }
        )

        propose_payload = ManualProposedPayload(
            generation_id=gen_id,
            candidate=cand.model_dump(mode="json"),
            upsert=upserted,
            superseded_candidate_id=superseded_id,
        )
        events.append(
            StudioEventEnvelope(
                session_id=session_id,
                event_type="manual_proposed",
                event_sequence=0,
                generation_id=gen_id,
                payload=propose_payload.model_dump(mode="json"),
                payload_schema_version=2,
                timestamp=now,
            )
        )
        if auto_accept:
            review_payload = ReviewRecordedPayload(
                generation_id=gen_id,
                candidate_id=cand.candidate_id,
                review_action=ReviewAction.accept,
                apply_scope=ApplyScope.all,
                selected_occurrence_keys=[],
                learn_intent=LearnIntent.none,
                review_target_text=right_text,
            )
            events.append(
                StudioEventEnvelope(
                    session_id=session_id,
                    event_type="review_recorded",
                    event_sequence=0,
                    generation_id=gen_id,
                    payload=review_payload.model_dump(mode="json"),
                    payload_schema_version=2,
                    timestamp=now,
                )
            )

        pre = PersistPreconditions(
            expected_last_event_sequence=expected_last,
            expected_current_generation_id=expected_gen,
            expected_transcript_identity_hash=expected_identity,
            expected_studio_session_rules_fingerprint=expected_rules_fp,
            check_generation_id=True,
        )
        try:
            self._session.persist_event_batch(
                transcript_path, doc, events, preconditions=pre
            )
        except GenerationCommitConflict:
            raise

        # Reload authoritative snapshot
        live = self._session.load_document(session_id)
        live_cand = next(
            (
                c
                for c in live.candidates
                if c.candidate_id == cand.candidate_id
                and c.generation_id == live.current_generation_id
            ),
            cand,
        )
        return ManualProposeResult(
            session=live,
            candidate=live_cand,
            upserted=upserted,
            auto_accepted=auto_accept,
        )
