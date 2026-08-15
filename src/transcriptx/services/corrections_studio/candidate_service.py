"""CorrectionsStudioCandidateService: thin facade for candidate generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from transcriptx.core.store.corrections_session_store import GenerationCommitConflict
from transcriptx.core.utils.logger import get_logger
from transcriptx.services.corrections_studio.candidate_commit import (
    commit_generation_batch,
)
from transcriptx.services.corrections_studio.candidate_detection import (
    pre_dedupe_aggregate,
    run_detectors,
)
from transcriptx.services.corrections_studio.candidate_diagnostics import (
    build_diagnostics,
    detector_counts_from_candidates,
    detector_counts_sum,
    log_generation,
)
from transcriptx.services.corrections_studio.candidate_generation_inputs import (
    GenerationInputs,
    load_generation_inputs,
)
from transcriptx.services.corrections_studio.candidate_llm import (
    run_soft_gated_discovery_and_merge,
)
from transcriptx.services.corrections_studio.candidate_mapping import (
    db_rule_to_engine_rule,
    engine_candidate_to_studio,
    enrich_occurrences,
)
from transcriptx.services.corrections_studio.candidate_materialize import (
    studio_candidates_from_annotated,
)
from transcriptx.services.corrections_studio.generation_manifest import (
    assemble_generation_manifest_for_run,
    build_generation_manifest,
    compute_llm_fingerprint,
    load_speaker_map_state,
    studio_session_rules_fingerprint,
)
from transcriptx.services.corrections_studio.identity import (
    compute_generation_manifest_hash,
)
from transcriptx.services.corrections_studio.llm.merge import annotate_engine_candidates
from transcriptx.services.corrections_studio.llm.review_migration import (
    build_review_migration_plan,
)
from transcriptx.services.corrections_studio.manual_carry_forward import (
    carry_forward_manual_candidates,
)
from transcriptx.services.corrections_studio.schema import (
    GenerationOrigin,
    SessionStartedPayload,
    StudioCandidate,
    StudioEventEnvelope,
    StudioSessionDocument,
)
from transcriptx.services.corrections_studio.session_service import (
    CorrectionsStudioSessionService,
)

# Re-exports for import compatibility (private helper names).
_GenerationInputs = GenerationInputs
_enrich_occurrences = enrich_occurrences
_db_rule_to_engine_rule = db_rule_to_engine_rule
_detector_counts_sum = detector_counts_sum
_detector_counts_from_candidates = detector_counts_from_candidates
_engine_candidate_to_studio = engine_candidate_to_studio

# Commonly patched names — keep bound on this module for existing tests.
from transcriptx.core.corrections.detect import (  # noqa: E402,F401
    detect_acronym_candidates,
    detect_consistency_candidates,
    detect_fuzzy_candidates,
    detect_memory_hits,
)
from transcriptx.core.corrections.memory import load_memory  # noqa: E402,F401
from transcriptx.core.utils.canonicalization import (  # noqa: E402,F401
    compute_transcript_identity_hash,
)
from transcriptx.core.utils.config import get_config  # noqa: E402,F401
from transcriptx.io import load_segments  # noqa: E402,F401
from transcriptx.services.corrections_studio.fuzzy_speaker_inputs import (  # noqa: E402,F401
    resolve_fuzzy_speaker_inputs,
)

logger = get_logger()


@dataclass(frozen=True)
class GenerateCandidatesResult:
    """Result of generate_candidates including optimistic-commit abort status."""

    candidates: List[StudioCandidate]
    commit_aborted: bool = False
    abort_reason: str = ""


class CorrectionsStudioCandidateService:
    def __init__(self, session_service: CorrectionsStudioSessionService) -> None:
        self._session = session_service

    def _ensure_session_started_event(
        self, session_id: str, doc: StudioSessionDocument, transcript_path: str
    ) -> None:
        if self._session.store.read_event_lines(session_id):
            return
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload = SessionStartedPayload(
            transcript_path=transcript_path,
            recorded_transcript_identity_hash=doc.recorded_transcript_identity_hash,
        )
        ev0 = StudioEventEnvelope(
            session_id=session_id,
            event_type="session_started",
            event_sequence=0,
            generation_id=None,
            payload=payload.model_dump(mode="json"),
            payload_schema_version=2,
            timestamp=now,
        )
        self._session.persist(transcript_path, doc, ev0)

    @staticmethod
    def _has_detector_generation(doc: StudioSessionDocument) -> bool:
        gen = doc.current_generation
        if gen is None:
            return False
        return gen.generation_origin == GenerationOrigin.detector

    def generate_candidates(
        self, session_id: str, force: bool = False
    ) -> GenerateCandidatesResult:
        doc = self._session.load_document(session_id)
        transcript_path = doc.transcript_path
        self._ensure_session_started_event(session_id, doc, transcript_path)
        doc = self._session.load_document(session_id)

        # H2: gate on detector generation, not mere presence of candidates
        # (manual-only sessions must still be able to Generate candidates).
        if self._has_detector_generation(doc) and not force:
            cur = doc.current_generation_id
            return GenerateCandidatesResult(
                candidates=[
                    c for c in doc.candidates if cur is None or c.generation_id == cur
                ]
            )

        expected_last = self._session.last_event_sequence(session_id)
        expected_gen = doc.current_generation_id
        expected_identity = doc.recorded_transcript_identity_hash
        expected_rules_fp = studio_session_rules_fingerprint(doc.rules)
        prior_candidates = list(doc.candidates)
        prior_reviews = list(doc.review_records)
        prior_gen_id = doc.current_generation_id

        inp = load_generation_inputs(
            transcript_path,
            doc,
            get_config_fn=get_config,
            load_segments_fn=load_segments,
            load_memory_fn=load_memory,
            resolve_fuzzy_fn=resolve_fuzzy_speaker_inputs,
            load_speaker_map_fn=load_speaker_map_state,
            db_rule_fn=_db_rule_to_engine_rule,
            compute_identity_hash_fn=compute_transcript_identity_hash,
        )
        mem_hits, ac, co, fz = run_detectors(
            inp,
            detect_memory_hits_fn=detect_memory_hits,
            detect_acronym_fn=detect_acronym_candidates,
            detect_consistency_fn=detect_consistency_candidates,
            detect_fuzzy_fn=detect_fuzzy_candidates,
        )
        pre_dedupe, total_pre = pre_dedupe_aggregate(mem_hits, ac, co, fz)
        det_annotated = annotate_engine_candidates(
            list(mem_hits) + list(ac) + list(co) + list(fz)
        )

        llm_merge = run_soft_gated_discovery_and_merge(
            inp, det_annotated, get_config_fn=get_config
        )
        merged = llm_merge.merged
        llm_result = llm_merge.llm_result
        llm_diag = llm_merge.llm_diag

        post_engines = [a.engine for a in merged]
        post_by_kind = detector_counts_from_candidates(post_engines)
        total_post = len(post_engines)
        diagnostics = build_diagnostics(
            inp, pre_dedupe, total_pre, post_by_kind, total_post
        )
        diagnostics = diagnostics.model_copy(update={"llm": llm_diag})

        new_gen = (doc.current_generation_id or 0) + 1
        manifest, mh = assemble_generation_manifest_for_run(
            inp=inp,
            doc=doc,
            llm_diag=llm_diag,
            llm_result=llm_result,
            build_manifest_fn=build_generation_manifest,
            compute_hash_fn=compute_generation_manifest_hash,
            compute_llm_fp_fn=compute_llm_fingerprint,
        )
        log_generation(
            transcript_path=transcript_path,
            transcript_key=inp.transcript_key,
            new_gen=new_gen,
            inp=inp,
            pre_dedupe=pre_dedupe,
            total_pre=total_pre,
            total_post=total_post,
            mh=mh,
        )

        llm_prov_map = {}
        for i, eng in enumerate(llm_result.candidates):
            if i < len(llm_result.provenance_by_index):
                llm_prov_map[f"{eng.proposed_wrong}|{eng.proposed_right}"] = (
                    llm_result.provenance_by_index[i]
                )

        studio_candidates = studio_candidates_from_annotated(
            merged, inp, new_gen, llm_prov_by_cand=llm_prov_map
        )
        return self._migrate_and_commit(
            session_id=session_id,
            transcript_path=transcript_path,
            doc=doc,
            new_gen=new_gen,
            manifest=manifest,
            mh=mh,
            diagnostics=diagnostics,
            studio_candidates=studio_candidates,
            prior_candidates=prior_candidates,
            prior_reviews=prior_reviews,
            prior_gen_id=prior_gen_id,
            expected_last=expected_last,
            expected_gen=expected_gen,
            expected_identity=expected_identity,
            expected_rules_fp=expected_rules_fp,
        )

    def _migrate_and_commit(
        self,
        *,
        session_id: str,
        transcript_path: str,
        doc: StudioSessionDocument,
        new_gen: int,
        manifest,
        mh: str,
        diagnostics,
        studio_candidates: List[StudioCandidate],
        prior_candidates,
        prior_reviews,
        prior_gen_id,
        expected_last,
        expected_gen,
        expected_identity,
        expected_rules_fp,
    ) -> GenerateCandidatesResult:
        mig = build_review_migration_plan(
            prior_candidates=prior_candidates,
            prior_reviews=prior_reviews,
            new_candidates=studio_candidates,
            prior_generation_id=prior_gen_id,
            new_generation_id=new_gen,
            rules_by_id=doc.rules,
        )
        # H1: explicit manual carry-forward (independent of detector migration).
        manual_cands, manual_reviews = carry_forward_manual_candidates(
            prior_candidates=prior_candidates,
            prior_reviews=prior_reviews,
            prior_generation_id=prior_gen_id,
            new_generation_id=new_gen,
        )
        # Avoid duplicating manuals that already appear in the detector set
        # under the same candidate_id (rare) or semantic identity.
        detector_ids = {c.candidate_id for c in studio_candidates}
        detector_sem = {
            c.semantic_identity_key
            for c in studio_candidates
            if c.semantic_identity_key
        }
        filtered_manuals = []
        filtered_manual_reviews = []
        kept_manual_ids = set()
        for mc in manual_cands:
            if mc.candidate_id in detector_ids:
                continue
            if mc.semantic_identity_key and mc.semantic_identity_key in detector_sem:
                continue
            filtered_manuals.append(mc)
            kept_manual_ids.add(mc.candidate_id)
        for mr in manual_reviews:
            if mr.candidate_id in kept_manual_ids:
                filtered_manual_reviews.append(mr)

        studio_candidates = list(studio_candidates) + filtered_manuals
        migration_payloads = list(mig.reviews) + filtered_manual_reviews

        if diagnostics.llm is not None:
            diagnostics = diagnostics.model_copy(
                update={
                    "llm": diagnostics.llm.model_copy(
                        update={"review_migration": mig.summary}
                    )
                }
            )
        # Retain prior-generation candidates for audit; listing defaults to current gen.
        historical = [c for c in prior_candidates if c.generation_id != new_gen]
        try:
            cands = commit_generation_batch(
                session_service=self._session,
                session_id=session_id,
                transcript_path=transcript_path,
                prior_doc=doc,
                new_gen=new_gen,
                manifest=manifest,
                mh=mh,
                diagnostics=diagnostics,
                studio_candidates=studio_candidates,
                migration_payloads=migration_payloads,
                expected_last_event_sequence=expected_last,
                expected_generation_id=expected_gen,
                expected_transcript_identity_hash=expected_identity,
                expected_rules_fp=expected_rules_fp,
                generation_origin=GenerationOrigin.detector,
                historical_candidates=historical,
            )
            return GenerateCandidatesResult(candidates=list(cands))
        except GenerationCommitConflict as exc:
            reason = getattr(exc, "reason", None) or str(exc) or "commit_conflict"
            logger.info(
                "corrections_generation_commit_aborted reason=%s",
                reason,
            )
            return GenerateCandidatesResult(
                candidates=list(prior_candidates),
                commit_aborted=True,
                abort_reason=str(reason),
            )
