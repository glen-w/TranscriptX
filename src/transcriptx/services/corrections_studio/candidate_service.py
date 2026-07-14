"""CorrectionsStudioCandidateService: detection → StudioGenerationRecord + candidates_generated events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from transcriptx.core.corrections.detect import (
    detect_acronym_candidates,
    detect_consistency_candidates,
    detect_fuzzy_candidates,
    detect_memory_hits,
    resolve_segment_id,
)
from transcriptx.core.corrections.memory import load_memory
from transcriptx.core.corrections.models import (
    Candidate as EngineCandidate,
    CorrectionRule,
    Occurrence,
)
from transcriptx.core.store.corrections_session_store import session_path_for_transcript
from transcriptx.core.utils.canonicalization import compute_transcript_identity_hash
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger
from transcriptx.io import load_segments
from transcriptx.io.speaker_map_resolver import SpeakerMapState
from transcriptx.services.corrections_studio.occurrence_keys import (
    stable_occurrence_key,
)
from transcriptx.services.corrections_studio.fuzzy_speaker_inputs import (
    FuzzySpeakerNameResolution,
    compute_fuzzy_skipped_reason,
    resolve_fuzzy_speaker_inputs,
)
from transcriptx.services.corrections_studio.generation_manifest import (
    STUDIO_DETECTOR_VERSION,
    build_generation_manifest,
    load_speaker_map_state,
)
from transcriptx.services.corrections_studio.identity import (
    compute_generation_manifest_hash,
)
from transcriptx.services.corrections_studio.schema import (
    CandidateGenerationDiagnostics,
    CandidatesGeneratedPayload,
    DetectorCountsByKind,
    ReviewStatus,
    SessionStartedPayload,
    StudioCandidate,
    StudioEventEnvelope,
    StudioGenerationRecord,
    StudioOccurrence,
    StudioSessionDocument,
)
from transcriptx.services.corrections_studio.session_service import (
    CorrectionsStudioSessionService,
)

logger = get_logger()


@dataclass(frozen=True)
class GenerateCandidatesResult:
    """Result of generate_candidates including optimistic-commit abort status."""

    candidates: List[StudioCandidate]
    commit_aborted: bool = False
    abort_reason: str = ""


def _detector_counts_sum(d: DetectorCountsByKind) -> int:
    return d.memory_hit + d.acronym + d.consistency + d.fuzzy + d.ner_variant + d.other


@dataclass(frozen=True)
class _GenerationInputs:
    segments: List[Dict[str, Any]]
    transcript_key: str
    corrections_config: Any
    memory: Any
    engine_rules: List[CorrectionRule]
    fuzzy_resolution: FuzzySpeakerNameResolution
    speaker_map_state: SpeakerMapState
    fuzzy_enabled: bool
    fuzzy_threshold: float
    consistency_threshold: float


def _enrich_occurrences(
    occurrences: List[Dict[str, Any]],
    segments: List[Dict[str, Any]],
    transcript_key: str,
    wrong_text: str,
) -> List[Dict[str, Any]]:
    seg_id_to_index: Dict[str, int] = {}
    for idx, seg in enumerate(segments):
        sid = resolve_segment_id(seg, transcript_key, segment_index=idx)
        seg_id_to_index[sid] = idx

    enriched = []
    for idx, occ in enumerate(occurrences):
        occ_dict = dict(occ)
        span = occ_dict.get("span")
        if span is not None and len(span) >= 2:
            span_start, span_end = int(span[0]), int(span[1])
        else:
            span_start, span_end = -1, -1
        base_key = stable_occurrence_key(
            occ_dict["segment_id"], span_start, span_end, wrong_text
        )
        if span is None:
            occ_dict["stable_occurrence_key"] = f"{base_key}_{idx}"
        else:
            occ_dict["stable_occurrence_key"] = base_key
        occ_dict["segment_index"] = seg_id_to_index.get(occ_dict["segment_id"], -1)
        enriched.append(occ_dict)
    return enriched


def _db_rule_to_engine_rule(rule_dict: Dict[str, Any]) -> CorrectionRule:
    from transcriptx.core.corrections.models import CorrectionConditions

    conditions = None
    if rule_dict.get("conditions_json"):
        conditions = CorrectionConditions(**rule_dict["conditions_json"])
    return CorrectionRule(
        id=rule_dict.get("id") or rule_dict.get("rule_hash"),
        type=rule_dict.get("type") or rule_dict.get("rule_type"),
        wrong=rule_dict.get("wrong") or rule_dict.get("wrong_variants_json") or [],
        right=rule_dict.get("right") or rule_dict.get("replacement_text") or "",
        scope=rule_dict.get("scope", "global"),
        confidence=rule_dict.get("confidence", 0.0),
        auto_apply=rule_dict.get("auto_apply", False),
        conditions=conditions,
        is_person_name=rule_dict.get("is_person_name", False),
    )


def _detector_counts_from_candidates(
    cands: List[EngineCandidate],
) -> DetectorCountsByKind:
    d = DetectorCountsByKind()
    for c in cands:
        k = str(c.kind)
        if k == "memory_hit":
            d.memory_hit += 1
        elif k == "acronym":
            d.acronym += 1
        elif k == "consistency":
            d.consistency += 1
        elif k == "fuzzy":
            d.fuzzy += 1
        elif k == "ner_variant":
            d.ner_variant += 1
        else:
            d.other += 1
    return d


def _engine_candidate_to_studio(
    c: EngineCandidate,
    *,
    generation_id: int,
    sources: Optional[List] = None,
    evidence: Any = None,
    llm_provenance: Any = None,
    semantic_identity_key: str = "",
) -> StudioCandidate:
    from transcriptx.services.corrections_studio.semantic_identity import (
        compute_semantic_identity_key,
        sources_from_kind,
    )

    occs: List[StudioOccurrence] = []
    for o in c.occurrences:
        occs.append(
            StudioOccurrence(
                segment_id=o.segment_id,
                stable_occurrence_key=o.occurrence_id or "",
                span=o.span,
                snippet=o.snippet or "",
                speaker=o.speaker,
                time_start=o.time_start,
                time_end=o.time_end,
                segment_index=-1,
            )
        )
    cid = c.candidate_id or ""
    src = list(sources) if sources else sources_from_kind(str(c.kind))
    sem = semantic_identity_key or compute_semantic_identity_key(
        c.proposed_wrong, c.proposed_right
    )
    return StudioCandidate(
        candidate_id=cid,
        generation_id=generation_id,
        kind=str(c.kind),
        wrong_text=c.proposed_wrong,
        right_text=c.proposed_right,
        confidence=c.confidence,
        rule_id=c.rule_id,
        occurrences=occs,
        review_status=ReviewStatus.pending,
        sources=src,
        evidence=evidence,
        llm_provenance=llm_provenance,
        semantic_identity_key=sem,
    )


class CorrectionsStudioCandidateService:
    def __init__(self, session_service: CorrectionsStudioSessionService) -> None:
        self._session = session_service

    def _ensure_session_started_event(
        self, session_id: str, doc: StudioSessionDocument, transcript_path: str
    ) -> None:
        if self._session.store.read_event_lines(session_id):
            return
        p0 = SessionStartedPayload(
            transcript_path=transcript_path,
            recorded_transcript_identity_hash=doc.recorded_transcript_identity_hash,
        )
        ev0 = StudioEventEnvelope(
            session_id=session_id,
            event_type="session_started",
            event_sequence=0,
            payload=p0.model_dump(mode="json"),
        )
        self._session.persist(transcript_path, doc, ev0)

    def _load_generation_inputs(
        self, transcript_path: str, doc: StudioSessionDocument
    ) -> _GenerationInputs:
        segments = load_segments(transcript_path)
        transcript_key = compute_transcript_identity_hash(segments)
        config = get_config()
        corrections_config = getattr(config.analysis, "corrections", None)
        memory = load_memory(
            transcript_path=transcript_path,
            transcript_decisions_path=str(session_path_for_transcript(transcript_path)),
        )
        engine_rules = [
            _db_rule_to_engine_rule(rule.model_dump()) for rule in memory.rules.values()
        ]
        for sr in doc.rules.values():
            try:
                engine_rules.append(
                    _db_rule_to_engine_rule(
                        {
                            "id": sr.rule_id,
                            "type": sr.rule_type,
                            "wrong": sr.wrong_variants,
                            "right": sr.replacement_text,
                            "scope": sr.scope,
                            "confidence": sr.confidence,
                            "auto_apply": sr.auto_apply,
                            "conditions_json": sr.conditions_json,
                            "is_person_name": sr.is_person_name,
                        }
                    )
                )
            except Exception:
                continue
        fuzzy_resolution = resolve_fuzzy_speaker_inputs(transcript_path, segments)
        speaker_map_state = load_speaker_map_state(transcript_path)
        fuzzy_enabled = bool(
            corrections_config and getattr(corrections_config, "enable_fuzzy", False)
        )
        fuzzy_threshold = (
            float(getattr(corrections_config, "fuzzy_similarity_threshold", 0.85))
            if corrections_config
            else 0.85
        )
        consistency_threshold = (
            float(getattr(corrections_config, "consistency_similarity_threshold", 0.0))
            if corrections_config
            else 0.0
        )
        return _GenerationInputs(
            segments=segments,
            transcript_key=transcript_key,
            corrections_config=corrections_config,
            memory=memory,
            engine_rules=engine_rules,
            fuzzy_resolution=fuzzy_resolution,
            speaker_map_state=speaker_map_state,
            fuzzy_enabled=fuzzy_enabled,
            fuzzy_threshold=fuzzy_threshold,
            consistency_threshold=consistency_threshold,
        )

    def _run_detectors(self, inp: _GenerationInputs) -> Tuple[
        List[EngineCandidate],
        List[EngineCandidate],
        List[EngineCandidate],
        List[EngineCandidate],
    ]:
        mem_hits = detect_memory_hits(
            inp.segments, inp.transcript_key, inp.engine_rules
        )
        ac: List[EngineCandidate] = []
        co: List[EngineCandidate] = []
        fz: List[EngineCandidate] = []
        if inp.corrections_config:
            ac = detect_acronym_candidates(
                inp.segments,
                inp.transcript_key,
                inp.corrections_config.known_acronyms,
                inp.corrections_config.known_org_phrases,
            )
            co = detect_consistency_candidates(
                inp.segments,
                inp.transcript_key,
                inp.corrections_config.consistency_similarity_threshold,
            )
            fz = detect_fuzzy_candidates(
                inp.segments,
                inp.transcript_key,
                list(inp.fuzzy_resolution.display_names_for_fuzzy),
                inp.fuzzy_threshold,
                inp.fuzzy_enabled,
            )
        return mem_hits, ac, co, fz

    def _pre_dedupe_aggregate(
        self,
        mem_hits: List[EngineCandidate],
        ac: List[EngineCandidate],
        co: List[EngineCandidate],
        fz: List[EngineCandidate],
    ) -> Tuple[DetectorCountsByKind, int]:
        pre_mem = _detector_counts_from_candidates(mem_hits)
        pre_ac = _detector_counts_from_candidates(ac)
        pre_co = _detector_counts_from_candidates(co)
        pre_fz = _detector_counts_from_candidates(fz)
        pre_dedupe = DetectorCountsByKind(
            memory_hit=pre_mem.memory_hit,
            acronym=pre_ac.acronym,
            consistency=pre_co.consistency,
            fuzzy=pre_fz.fuzzy,
            ner_variant=pre_mem.ner_variant
            + pre_ac.ner_variant
            + pre_co.ner_variant
            + pre_fz.ner_variant,
            other=pre_mem.other + pre_ac.other + pre_co.other + pre_fz.other,
        )
        total_pre = len(mem_hits) + len(ac) + len(co) + len(fz)
        return pre_dedupe, total_pre

    def _build_diagnostics(
        self,
        inp: _GenerationInputs,
        pre_dedupe: DetectorCountsByKind,
        total_pre: int,
        post_by_kind: DetectorCountsByKind,
        total_post: int,
    ) -> CandidateGenerationDiagnostics:
        fuzzy_named_count = len(inp.fuzzy_resolution.display_names_for_fuzzy)
        skipped = compute_fuzzy_skipped_reason(
            inp.fuzzy_enabled, inp.fuzzy_resolution, fuzzy_named_count
        )
        known_acronyms = (
            list(getattr(inp.corrections_config, "known_acronyms", []) or [])
            if inp.corrections_config
            else []
        )
        org_phrases = (
            getattr(inp.corrections_config, "known_org_phrases", {}) or {}
            if inp.corrections_config
            else {}
        )
        return CandidateGenerationDiagnostics(
            pre_dedupe=pre_dedupe,
            total_pre_dedupe=total_pre,
            post_dedupe_counts_by_kind=post_by_kind,
            total_after_dedupe=total_post,
            fuzzy_enabled=inp.fuzzy_enabled,
            fuzzy_similarity_threshold=inp.fuzzy_threshold,
            consistency_similarity_threshold=inp.consistency_threshold,
            known_acronym_count=len(known_acronyms),
            known_org_phrase_count=len(org_phrases),
            fuzzy_named_speaker_count=fuzzy_named_count,
            fuzzy_skipped_reason=skipped,
            observed_named_speaker_count=len(
                inp.fuzzy_resolution.observed_named_speakers
            ),
        )

    def _build_manifest_and_log(
        self,
        *,
        transcript_path: str,
        transcript_key: str,
        new_gen: int,
        inp: _GenerationInputs,
        pre_dedupe: DetectorCountsByKind,
        total_pre: int,
        total_post: int,
        mh: str,
    ) -> None:
        fuzzy_named_count = len(inp.fuzzy_resolution.display_names_for_fuzzy)
        log_payload = {
            "event": "corrections_studio_generation",
            "transcript_path": transcript_path,
            "transcript_identity_hash": transcript_key[:16],
            "generation_id": new_gen,
            "pre_dedupe": pre_dedupe.model_dump(mode="json"),
            "total_pre_dedupe": total_pre,
            "total_after_dedupe": total_post,
            "fuzzy_enabled": inp.fuzzy_enabled,
            "fuzzy_named_speaker_count": fuzzy_named_count,
            "generation_manifest_hash_prefix": mh[:12],
        }
        logger.info("%s", json.dumps(log_payload, sort_keys=True))

    def _studio_candidates_from_annotated(
        self,
        annotated: List[Any],
        inp: _GenerationInputs,
        new_gen: int,
        llm_prov_by_cand: Optional[Dict[str, Any]] = None,
    ) -> List[StudioCandidate]:
        from transcriptx.services.corrections_studio.llm.confidence import (
            ranking_confidence_from_evidence,
        )
        from transcriptx.services.corrections_studio.semantic_identity import (
            compute_semantic_identity_key,
            condition_sig_from_rule_id,
        )

        rules_by_id = {r.id: r for r in inp.engine_rules if r.id}
        llm_prov_by_cand = llm_prov_by_cand or {}
        studio_candidates: List[StudioCandidate] = []
        for ann in annotated:
            c = ann.engine
            occ_dicts = [occ.model_dump() for occ in c.occurrences]
            enriched = _enrich_occurrences(
                occ_dicts,
                inp.segments,
                inp.transcript_key,
                c.proposed_wrong,
            )
            new_occs: List[Occurrence] = []
            for o in enriched:
                span = o.get("span")
                st = None
                if span is not None and len(span) >= 2:
                    st = (int(span[0]), int(span[1]))
                new_occs.append(
                    Occurrence(
                        segment_id=o["segment_id"],
                        speaker=o.get("speaker"),
                        time_start=o.get("time_start"),
                        time_end=o.get("time_end"),
                        span=st,
                        snippet=o.get("snippet", ""),
                        occurrence_id=o.get("stable_occurrence_key"),
                    )
                )
            conf = ranking_confidence_from_evidence(ann.evidence)
            c2 = EngineCandidate(
                candidate_id=c.candidate_id,
                rule_id=c.rule_id,
                proposed_wrong=c.proposed_wrong,
                proposed_right=c.proposed_right,
                kind=c.kind,
                confidence=conf,
                occurrences=new_occs,
            )
            cond = condition_sig_from_rule_id(c2.rule_id, rules_by_id)
            sem = compute_semantic_identity_key(
                c2.proposed_wrong, c2.proposed_right, condition_sig=cond
            )
            sc = _engine_candidate_to_studio(
                c2,
                generation_id=new_gen,
                sources=ann.sources,
                evidence=ann.evidence,
                llm_provenance=llm_prov_by_cand.get(
                    f"{c2.proposed_wrong}|{c2.proposed_right}"
                ),
                semantic_identity_key=sem,
            )
            updated_occs: List[StudioOccurrence] = []
            for i, occ in enumerate(sc.occurrences):
                si = (
                    int(enriched[i].get("segment_index", -1))
                    if i < len(enriched)
                    else -1
                )
                updated_occs.append(occ.model_copy(update={"segment_index": si}))
            studio_candidates.append(
                sc.model_copy(update={"occurrences": updated_occs})
            )
        return studio_candidates

    def _commit_generation_batch(
        self,
        *,
        session_id: str,
        transcript_path: str,
        prior_doc: StudioSessionDocument,
        new_gen: int,
        manifest: Any,
        mh: str,
        diagnostics: CandidateGenerationDiagnostics,
        studio_candidates: List[StudioCandidate],
        migration_payloads: List[Any],
        expected_last_event_sequence: int,
        expected_generation_id: Optional[int],
        expected_transcript_identity_hash: str,
        expected_rules_fp: str,
    ) -> List[StudioCandidate]:
        from transcriptx.services.corrections_studio.schema import (
            ReviewAction,
            StudioReviewRecord,
        )
        from transcriptx.services.corrections_studio.session_service import (
            PersistPreconditions,
        )

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        review_records = [
            r for r in prior_doc.review_records if r.generation_id != new_gen
        ]
        status_by_cand: Dict[str, ReviewStatus] = {}
        for mp in migration_payloads:
            action = mp.review_action
            if action in (ReviewAction.accept, ReviewAction.learn):
                st = ReviewStatus.accepted
            elif action == ReviewAction.reject:
                st = ReviewStatus.rejected
            else:
                st = ReviewStatus.pending
            status_by_cand[mp.candidate_id] = st
            review_records.append(
                StudioReviewRecord(
                    session_id=session_id,
                    generation_id=new_gen,
                    candidate_id=mp.candidate_id,
                    review_action=action,
                    apply_scope=mp.apply_scope,
                    selected_occurrence_keys=list(mp.selected_occurrence_keys),
                    learn_intent=mp.learn_intent,
                    learn_rule_id=mp.learn_rule_id,
                    review_target_text=mp.review_target_text,
                    recorded_at=now,
                    event_sequence=0,
                    migrated_from_generation_id=mp.migrated_from_generation_id,
                )
            )

        cands = [
            c.model_copy(
                update={
                    "review_status": status_by_cand.get(
                        c.candidate_id, ReviewStatus.pending
                    )
                }
            )
            for c in studio_candidates
        ]
        doc = prior_doc.model_copy(
            update={
                "current_generation_id": new_gen,
                "current_generation": StudioGenerationRecord(
                    generation_id=new_gen,
                    generation_manifest=manifest,
                    generation_manifest_hash=mh,
                    candidate_ids=[c.candidate_id for c in cands],
                    completed_at=now,
                    generation_diagnostics=diagnostics,
                ),
                "candidates": cands,
                "review_records": review_records,
                "updated_at": now,
                "studio_schema_version": 2,
            }
        )
        if not doc.created_at:
            doc = doc.model_copy(update={"created_at": now})

        cand_payload = CandidatesGeneratedPayload(
            generation_id=new_gen,
            generation_manifest=manifest,
            generation_manifest_hash=mh,
            candidate_ids=[c.candidate_id for c in cands],
            candidates=[c.model_dump(mode="json") for c in cands],
            diagnostics=diagnostics,
        )
        events: List[StudioEventEnvelope] = [
            StudioEventEnvelope(
                session_id=session_id,
                event_type="candidates_generated",
                event_sequence=0,
                generation_id=new_gen,
                payload=cand_payload.model_dump(mode="json"),
                payload_schema_version=2,
                timestamp=now,
            )
        ]
        for mp in migration_payloads:
            events.append(
                StudioEventEnvelope(
                    session_id=session_id,
                    event_type="review_recorded",
                    event_sequence=0,
                    generation_id=new_gen,
                    payload=mp.model_dump(mode="json"),
                    payload_schema_version=2,
                    timestamp=now,
                )
            )
        pre = PersistPreconditions(
            expected_last_event_sequence=expected_last_event_sequence,
            expected_current_generation_id=expected_generation_id,
            expected_transcript_identity_hash=expected_transcript_identity_hash,
            expected_studio_session_rules_fingerprint=expected_rules_fp,
            check_generation_id=True,
        )
        self._session.persist_event_batch(
            transcript_path, doc, events, preconditions=pre
        )
        return cands

    def generate_candidates(
        self, session_id: str, force: bool = False
    ) -> GenerateCandidatesResult:
        from transcriptx.core.store.corrections_session_store import (
            GenerationCommitConflict,
        )
        from transcriptx.services.corrections_studio.generation_manifest import (
            CONTEXT_PACK_VERSION,
            LLM_PROMPT_VERSION,
            LLM_SCHEMA_VERSION,
            compute_llm_fingerprint,
            studio_session_rules_fingerprint,
        )
        from transcriptx.services.corrections_studio.llm.discovery import (
            LlmDiscoveryResult,
            run_llm_discovery,
        )
        from transcriptx.services.corrections_studio.llm.merge import (
            annotate_engine_candidates,
            cross_kind_merge,
        )
        from transcriptx.services.corrections_studio.llm.review_migration import (
            build_review_migration_plan,
        )
        from transcriptx.services.corrections_studio.schema import (
            CandidateSource,
            LlmGenerationDiagnostics,
        )

        doc = self._session.load_document(session_id)
        transcript_path = doc.transcript_path
        self._ensure_session_started_event(session_id, doc, transcript_path)
        doc = self._session.load_document(session_id)

        if doc.candidates and not force:
            return GenerateCandidatesResult(candidates=list(doc.candidates))

        expected_last = self._session.last_event_sequence(session_id)
        expected_gen = doc.current_generation_id
        expected_identity = doc.recorded_transcript_identity_hash
        expected_rules_fp = studio_session_rules_fingerprint(doc.rules)
        prior_candidates = list(doc.candidates)
        prior_reviews = list(doc.review_records)
        prior_gen_id = doc.current_generation_id

        inp = self._load_generation_inputs(transcript_path, doc)
        mem_hits, ac, co, fz = self._run_detectors(inp)
        pre_dedupe, total_pre = self._pre_dedupe_aggregate(mem_hits, ac, co, fz)
        det_annotated = annotate_engine_candidates(
            list(mem_hits) + list(ac) + list(co) + list(fz)
        )

        config = get_config()
        llm_cfg = getattr(config, "llm", None)
        corrections_llm = (
            getattr(inp.corrections_config, "llm", None)
            if inp.corrections_config
            else None
        )
        memory_pairs = [
            (",".join(r.wrong), r.right)
            for r in inp.engine_rules
            if getattr(r, "wrong", None)
        ]
        speaker_names = list(inp.fuzzy_resolution.display_names_for_fuzzy)
        known_acronyms = (
            list(getattr(inp.corrections_config, "known_acronyms", []) or [])
            if inp.corrections_config
            else []
        )
        org_phrases = (
            dict(getattr(inp.corrections_config, "known_org_phrases", {}) or {})
            if inp.corrections_config
            else {}
        )
        try:
            llm_result = run_llm_discovery(
                segments=inp.segments,
                transcript_key=inp.transcript_key,
                llm_cfg=llm_cfg,
                corrections_llm=corrections_llm,
                speaker_names=speaker_names,
                memory_pairs=memory_pairs,
                known_acronyms=known_acronyms,
                known_org_phrases=org_phrases,
            )
        except Exception:
            # Belt-and-suspenders: discovery already soft-gates, but never let
            # unexpected escape kill deterministic candidates.
            logger.exception("corrections_llm_discovery_call_site_guard")
            llm_result = LlmDiscoveryResult(
                candidates=[],
                diagnostics=LlmGenerationDiagnostics(
                    enabled=bool(
                        corrections_llm and getattr(corrections_llm, "enabled", False)
                    ),
                    attempted=True,
                    available=False,
                    outcome="failed",
                    error_code="unexpected_error",
                ),
                provenance_by_index=[],
                evidence_by_index=[],
                llm_fingerprint_material={},
            )
        llm_annotated = annotate_engine_candidates(
            llm_result.candidates,
            default_source=CandidateSource.llm_discovery,
        )
        for i, ann in enumerate(llm_annotated):
            if (
                i < len(llm_result.evidence_by_index)
                and llm_result.evidence_by_index[i]
            ):
                ann.evidence = llm_result.evidence_by_index[i]

        rules_by_id = {r.id: r for r in inp.engine_rules if r.id}
        merged, conflicts = cross_kind_merge(
            det_annotated + llm_annotated, rules_by_id=rules_by_id
        )
        llm_diag = llm_result.diagnostics
        llm_diag.overlapping_conflicts = conflicts
        llm_diag.candidates_after_merge = len(
            [a for a in merged if CandidateSource.llm_discovery in a.sources]
        )

        post_engines = [a.engine for a in merged]
        post_by_kind = _detector_counts_from_candidates(post_engines)
        total_post = len(post_engines)
        diagnostics = self._build_diagnostics(
            inp, pre_dedupe, total_pre, post_by_kind, total_post
        )
        diagnostics = diagnostics.model_copy(update={"llm": llm_diag})

        new_gen = (doc.current_generation_id or 0) + 1
        llm_fp = ""
        llm_prompt_v = ""
        llm_schema_v = ""
        ctx_v = ""
        if llm_diag.enabled:
            mat = llm_result.llm_fingerprint_material
            if mat:
                llm_fp = compute_llm_fingerprint(**mat)
            llm_prompt_v = LLM_PROMPT_VERSION
            llm_schema_v = LLM_SCHEMA_VERSION
            ctx_v = CONTEXT_PACK_VERSION

        manifest = build_generation_manifest(
            transcript_identity_hash=inp.transcript_key,
            corrections_config=inp.corrections_config,
            memory=inp.memory,
            studio_rules=doc.rules,
            speaker_map_state=inp.speaker_map_state,
            detector_version=STUDIO_DETECTOR_VERSION,
            llm_fingerprint=llm_fp,
            llm_prompt_version=llm_prompt_v,
            llm_schema_version=llm_schema_v,
            context_pack_version=ctx_v,
        )
        mh = compute_generation_manifest_hash(manifest)
        self._build_manifest_and_log(
            transcript_path=transcript_path,
            transcript_key=inp.transcript_key,
            new_gen=new_gen,
            inp=inp,
            pre_dedupe=pre_dedupe,
            total_pre=total_pre,
            total_post=total_post,
            mh=mh,
        )

        llm_prov_map: Dict[str, Any] = {}
        for i, eng in enumerate(llm_result.candidates):
            if i < len(llm_result.provenance_by_index):
                llm_prov_map[f"{eng.proposed_wrong}|{eng.proposed_right}"] = (
                    llm_result.provenance_by_index[i]
                )

        studio_candidates = self._studio_candidates_from_annotated(
            merged, inp, new_gen, llm_prov_by_cand=llm_prov_map
        )
        mig = build_review_migration_plan(
            prior_candidates=prior_candidates,
            prior_reviews=prior_reviews,
            new_candidates=studio_candidates,
            prior_generation_id=prior_gen_id,
            new_generation_id=new_gen,
            rules_by_id=doc.rules,
        )
        if diagnostics.llm is not None:
            diagnostics = diagnostics.model_copy(
                update={
                    "llm": diagnostics.llm.model_copy(
                        update={"review_migration": mig.summary}
                    )
                }
            )
        try:
            cands = self._commit_generation_batch(
                session_id=session_id,
                transcript_path=transcript_path,
                prior_doc=doc,
                new_gen=new_gen,
                manifest=manifest,
                mh=mh,
                diagnostics=diagnostics,
                studio_candidates=studio_candidates,
                migration_payloads=mig.reviews,
                expected_last_event_sequence=expected_last,
                expected_generation_id=expected_gen,
                expected_transcript_identity_hash=expected_identity,
                expected_rules_fp=expected_rules_fp,
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
