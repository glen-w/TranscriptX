"""Materialize Studio candidates from annotated engine candidates."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transcriptx.core.corrections.models import (
    Candidate as EngineCandidate,
    Occurrence,
)
from transcriptx.services.corrections_studio.candidate_generation_inputs import (
    GenerationInputs,
)
from transcriptx.services.corrections_studio.candidate_mapping import (
    engine_candidate_to_studio,
    enrich_occurrences,
)
from transcriptx.services.corrections_studio.schema import (
    StudioCandidate,
    StudioOccurrence,
)


def studio_candidates_from_annotated(
    annotated: List[Any],
    inp: GenerationInputs,
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
        enriched = enrich_occurrences(
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
        sc = engine_candidate_to_studio(
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
            si = int(enriched[i].get("segment_index", -1)) if i < len(enriched) else -1
            updated_occs.append(occ.model_copy(update={"segment_index": si}))
        studio_candidates.append(sc.model_copy(update={"occurrences": updated_occs}))
    return studio_candidates
