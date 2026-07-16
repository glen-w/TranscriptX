"""Mapping helpers between engine corrections models and Studio candidates."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transcriptx.core.corrections.detect import resolve_segment_id
from transcriptx.core.corrections.models import (
    Candidate as EngineCandidate,
    CorrectionRule,
)
from transcriptx.services.corrections_studio.occurrence_keys import (
    stable_occurrence_key,
)
from transcriptx.services.corrections_studio.schema import (
    ReviewStatus,
    StudioCandidate,
    StudioOccurrence,
)


def enrich_occurrences(
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


def db_rule_to_engine_rule(rule_dict: Dict[str, Any]) -> CorrectionRule:
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


def engine_candidate_to_studio(
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
