"""CorrectionsStudioCandidateService: detection → StudioGenerationRecord + candidates_generated events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

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
from transcriptx.core.corrections.workflow import dedupe_candidates
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
    c: EngineCandidate, *, generation_id: int
) -> StudioCandidate:
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
            event_sequence=1,
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

    def _studio_candidates_from_deduped(
        self,
        candidates_deduped: List[EngineCandidate],
        inp: _GenerationInputs,
        new_gen: int,
    ) -> List[StudioCandidate]:
        studio_candidates: List[StudioCandidate] = []
        for c in candidates_deduped:
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
            c2 = EngineCandidate(
                candidate_id=c.candidate_id,
                rule_id=c.rule_id,
                proposed_wrong=c.proposed_wrong,
                proposed_right=c.proposed_right,
                kind=c.kind,
                confidence=c.confidence,
                occurrences=new_occs,
            )
            sc = _engine_candidate_to_studio(c2, generation_id=new_gen)
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

    def _persist_candidates_generated(
        self,
        *,
        session_id: str,
        transcript_path: str,
        doc: StudioSessionDocument,
        new_gen: int,
        manifest: Any,
        mh: str,
        diagnostics: CandidateGenerationDiagnostics,
        studio_candidates: List[StudioCandidate],
    ) -> None:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        doc.current_generation_id = new_gen
        doc.current_generation = StudioGenerationRecord(
            generation_id=new_gen,
            generation_manifest=manifest,
            generation_manifest_hash=mh,
            candidate_ids=[c.candidate_id for c in studio_candidates],
            completed_at=now,
            generation_diagnostics=diagnostics,
        )
        doc.candidates = studio_candidates
        doc.updated_at = now
        if not doc.created_at:
            doc.created_at = doc.updated_at
        cand_payload = CandidatesGeneratedPayload(
            generation_id=new_gen,
            generation_manifest=manifest,
            generation_manifest_hash=mh,
            candidate_ids=[c.candidate_id for c in studio_candidates],
            candidates=[c.model_dump(mode="json") for c in studio_candidates],
            diagnostics=diagnostics,
        )
        seq = self._session.next_event_sequence(session_id)
        event = StudioEventEnvelope(
            session_id=session_id,
            event_type="candidates_generated",
            event_sequence=seq,
            generation_id=new_gen,
            payload=cand_payload.model_dump(mode="json"),
        )
        self._session.persist(transcript_path, doc, event)

    def generate_candidates(
        self, session_id: str, force: bool = False
    ) -> List[StudioCandidate]:
        doc = self._session.load_document(session_id)
        transcript_path = doc.transcript_path
        self._ensure_session_started_event(session_id, doc, transcript_path)
        if doc.candidates and not force:
            return list(doc.candidates)

        inp = self._load_generation_inputs(transcript_path, doc)
        mem_hits, ac, co, fz = self._run_detectors(inp)
        pre_dedupe, total_pre = self._pre_dedupe_aggregate(mem_hits, ac, co, fz)

        candidates_eng: List[EngineCandidate] = []
        candidates_eng.extend(mem_hits)
        candidates_eng.extend(ac)
        candidates_eng.extend(co)
        candidates_eng.extend(fz)

        rules_by_id = {r.id: r for r in inp.engine_rules if r.id}
        candidates_deduped = dedupe_candidates(candidates_eng, rules_by_id=rules_by_id)
        post_by_kind = _detector_counts_from_candidates(candidates_deduped)
        total_post = len(candidates_deduped)
        assert _detector_counts_sum(post_by_kind) == total_post

        diagnostics = self._build_diagnostics(
            inp, pre_dedupe, total_pre, post_by_kind, total_post
        )

        new_gen = (doc.current_generation_id or 0) + 1
        manifest = build_generation_manifest(
            transcript_identity_hash=inp.transcript_key,
            corrections_config=inp.corrections_config,
            memory=inp.memory,
            studio_rules=doc.rules,
            speaker_map_state=inp.speaker_map_state,
            detector_version=STUDIO_DETECTOR_VERSION,
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

        studio_candidates = self._studio_candidates_from_deduped(
            candidates_deduped, inp, new_gen
        )
        assert len(studio_candidates) == total_post
        assert _detector_counts_sum(post_by_kind) == len(studio_candidates)

        self._persist_candidates_generated(
            session_id=session_id,
            transcript_path=transcript_path,
            doc=doc,
            new_gen=new_gen,
            manifest=manifest,
            mh=mh,
            diagnostics=diagnostics,
            studio_candidates=studio_candidates,
        )
        return studio_candidates
