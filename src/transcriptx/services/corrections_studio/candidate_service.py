"""CorrectionsStudioCandidateService: detection → StudioGenerationRecord + candidates_generated events."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

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
from transcriptx.core.corrections.workflow import _dedupe_candidates
from transcriptx.core.utils.canonicalization import compute_transcript_identity_hash
from transcriptx.core.utils.config import get_config
from transcriptx.core.store.corrections_session_store import session_path_for_transcript
from transcriptx.io import load_segments
from transcriptx.services.corrections_studio.identity import (
    compute_generation_manifest_hash,
)
from transcriptx.services.corrections_studio.schema import (
    CandidatesGeneratedPayload,
    GenerationManifest,
    ReviewStatus,
    SessionStartedPayload,
    StudioCandidate,
    StudioEventEnvelope,
    StudioGenerationRecord,
    StudioOccurrence,
)
from transcriptx.services.corrections_studio.session_service import (
    CorrectionsStudioSessionService,
)

STUDIO_DETECTOR_VERSION = "1"


def _stable_occurrence_key(
    segment_id: str, span_start: int, span_end: int, wrong_text: str
) -> str:
    sig = f"{segment_id}:{span_start}:{span_end}:{wrong_text}"
    return hashlib.sha1(sig.encode("utf-8")).hexdigest()


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
        base_key = _stable_occurrence_key(
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


def _memory_fingerprint(memory: Any) -> str:
    ids = sorted((memory.rules or {}).keys())
    raw = ",".join(ids).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def _config_fingerprint(corrections_config: Any) -> str:
    if corrections_config is None:
        return ""
    payload = {
        "acronyms": list(getattr(corrections_config, "known_acronyms", []) or []),
        "org_phrases": sorted(
            (getattr(corrections_config, "known_org_phrases", {}) or {}).keys()
        ),
        "consistency": getattr(
            corrections_config, "consistency_similarity_threshold", None
        ),
        "fuzzy": getattr(corrections_config, "fuzzy_similarity_threshold", None),
        "enable_fuzzy": getattr(corrections_config, "enable_fuzzy", False),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:32]


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

    def generate_candidates(
        self, session_id: str, force: bool = False
    ) -> List[StudioCandidate]:
        doc = self._session.load_document(session_id)
        transcript_path = doc.transcript_path

        if not self._session.store.read_event_lines(session_id):
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

        if doc.candidates and not force:
            return list(doc.candidates)

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

        candidates_eng: List[EngineCandidate] = []
        candidates_eng.extend(
            detect_memory_hits(segments, transcript_key, engine_rules)
        )

        if corrections_config:
            candidates_eng.extend(
                detect_acronym_candidates(
                    segments,
                    transcript_key,
                    corrections_config.known_acronyms,
                    corrections_config.known_org_phrases,
                )
            )
            candidates_eng.extend(
                detect_consistency_candidates(
                    segments,
                    transcript_key,
                    corrections_config.consistency_similarity_threshold,
                )
            )
            speaker_names: List[str] = []
            candidates_eng.extend(
                detect_fuzzy_candidates(
                    segments,
                    transcript_key,
                    speaker_names,
                    getattr(corrections_config, "fuzzy_similarity_threshold", 0.85),
                    getattr(corrections_config, "enable_fuzzy", False),
                )
            )

        rules_by_id = {r.id: r for r in engine_rules if r.id}
        candidates_eng = _dedupe_candidates(candidates_eng, rules_by_id=rules_by_id)

        new_gen = (doc.current_generation_id or 0) + 1

        manifest = GenerationManifest(
            transcript_identity_hash=transcript_key,
            detector_version=STUDIO_DETECTOR_VERSION,
            corrections_config_fingerprint=_config_fingerprint(corrections_config),
            memory_rule_fingerprint=_memory_fingerprint(memory),
        )
        mh = compute_generation_manifest_hash(manifest)

        studio_candidates: List[StudioCandidate] = []
        for c in candidates_eng:
            occ_dicts = [occ.model_dump() for occ in c.occurrences]
            enriched = _enrich_occurrences(
                occ_dicts, segments, transcript_key, c.proposed_wrong
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

        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        doc.current_generation_id = new_gen
        doc.current_generation = StudioGenerationRecord(
            generation_id=new_gen,
            generation_manifest=manifest,
            generation_manifest_hash=mh,
            candidate_ids=[c.candidate_id for c in studio_candidates],
            completed_at=now,
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
        return studio_candidates
