"""Cross-kind merge for deterministic + LLM correction candidates."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from transcriptx.core.corrections.models import Candidate as EngineCandidate
from transcriptx.core.corrections.models import CorrectionRule, Occurrence
from transcriptx.core.corrections.workflow import dedupe_candidates
from transcriptx.services.corrections_studio.llm.confidence import (
    evidence_for_detector_kind,
    merge_evidence,
    ranking_confidence_from_evidence,
)
from transcriptx.services.corrections_studio.schema import (
    CandidateEvidence,
    CandidateSource,
)
from transcriptx.services.corrections_studio.semantic_identity import (
    condition_sig_from_rule_id,
    merge_sources,
    sources_from_kind,
)

_KIND_RANK = {
    "memory_hit": 0,
    "acronym": 1,
    "consistency": 2,
    "fuzzy": 3,
    "ner_variant": 4,
}


def _occ_key(o: Occurrence) -> Tuple:
    span = o.span or (-1, -1)
    return (o.segment_id, span[0], span[1])


def _merge_occurrences(a: List[Occurrence], b: List[Occurrence]) -> List[Occurrence]:
    seen = set()
    out: List[Occurrence] = []
    for o in list(a) + list(b):
        k = _occ_key(o)
        if k in seen:
            continue
        seen.add(k)
        out.append(o)
    return out


class AnnotatedCandidate:
    __slots__ = ("engine", "sources", "evidence")

    def __init__(
        self,
        engine: EngineCandidate,
        sources: List[CandidateSource],
        evidence: Optional[CandidateEvidence],
    ) -> None:
        self.engine = engine
        self.sources = sources
        self.evidence = evidence


def annotate_engine_candidates(
    candidates: List[EngineCandidate],
    *,
    default_source: Optional[CandidateSource] = None,
    llm_evidence: Optional[CandidateEvidence] = None,
) -> List[AnnotatedCandidate]:
    out: List[AnnotatedCandidate] = []
    for c in candidates:
        sources = sources_from_kind(c.kind)
        if default_source and default_source not in sources:
            sources = merge_sources(sources, [default_source])
        if c.kind == "ner_variant" and CandidateSource.llm_discovery not in sources:
            sources = merge_sources(sources, [CandidateSource.llm_discovery])
        ev = (
            llm_evidence
            if c.kind == "ner_variant" and llm_evidence
            else evidence_for_detector_kind(c.kind)
        )
        out.append(AnnotatedCandidate(c, sources, ev))
    return out


def cross_kind_merge(
    annotated: List[AnnotatedCandidate],
    *,
    rules_by_id: Optional[Dict[str, CorrectionRule]] = None,
) -> Tuple[List[AnnotatedCandidate], int]:
    """
    Merge by (wrong, right, condition) ignoring kind.
    Returns merged annotations and overlapping_conflicts count.
    """
    rules_by_id = rules_by_id or {}
    buckets: Dict[Tuple[str, str, str], AnnotatedCandidate] = {}
    conflicts = 0
    span_rights: Dict[Tuple, str] = {}

    for item in annotated:
        c = item.engine
        cond = condition_sig_from_rule_id(c.rule_id, rules_by_id)
        key = (c.proposed_wrong.casefold(), c.proposed_right.casefold(), cond)
        existing = buckets.get(key)
        if existing is None:
            buckets[key] = item
        else:
            ex = existing.engine
            rank_new = _KIND_RANK.get(c.kind, 99)
            rank_old = _KIND_RANK.get(ex.kind, 99)
            winner_engine = ex if rank_old <= rank_new else c
            loser_engine = c if winner_engine is ex else ex
            winner_item = existing if winner_engine is ex else item
            loser_item = item if winner_engine is ex else existing
            merged_sources = merge_sources(winner_item.sources, loser_item.sources)
            merged_ev = merge_evidence(winner_item.evidence, loser_item.evidence)
            winner_engine = EngineCandidate(
                candidate_id=winner_engine.candidate_id,
                rule_id=winner_engine.rule_id or loser_engine.rule_id,
                proposed_wrong=winner_engine.proposed_wrong,
                proposed_right=winner_engine.proposed_right,
                kind=winner_engine.kind,
                confidence=ranking_confidence_from_evidence(merged_ev),
                occurrences=_merge_occurrences(
                    winner_engine.occurrences, loser_engine.occurrences
                ),
            )
            buckets[key] = AnnotatedCandidate(winner_engine, merged_sources, merged_ev)

        for o in c.occurrences:
            sk = _occ_key(o)
            prev = span_rights.get(sk)
            if prev is not None and prev != c.proposed_right.casefold():
                conflicts += 1
            else:
                span_rights[sk] = c.proposed_right.casefold()

    # Mark disputed when same span maps to multiple rights still present
    by_span: Dict[Tuple, List[AnnotatedCandidate]] = {}
    for item in buckets.values():
        for o in item.engine.occurrences:
            by_span.setdefault(_occ_key(o), []).append(item)
    for items in by_span.values():
        rights = {i.engine.proposed_right.casefold() for i in items}
        if len(rights) > 1:
            # Mark lower-precedence as disputed
            ordered = sorted(items, key=lambda i: _KIND_RANK.get(i.engine.kind, 99))
            for loser in ordered[1:]:
                loser.evidence = merge_evidence(loser.evidence, disputed=True)
                loser.engine = EngineCandidate(
                    candidate_id=loser.engine.candidate_id,
                    rule_id=loser.engine.rule_id,
                    proposed_wrong=loser.engine.proposed_wrong,
                    proposed_right=loser.engine.proposed_right,
                    kind=loser.engine.kind,
                    confidence=ranking_confidence_from_evidence(loser.evidence),
                    occurrences=loser.engine.occurrences,
                )

    merged_list = list(buckets.values())
    engines = [a.engine for a in merged_list]
    deduped = dedupe_candidates(engines, rules_by_id=rules_by_id)
    # Reattach annotations by (kind, wrong, right)
    index = {
        (
            a.engine.kind,
            a.engine.proposed_wrong.casefold(),
            a.engine.proposed_right.casefold(),
        ): a
        for a in merged_list
    }
    final: List[AnnotatedCandidate] = []
    for e in deduped:
        key = (e.kind, e.proposed_wrong.casefold(), e.proposed_right.casefold())
        ann = index.get(key)
        if ann is None:
            final.append(
                AnnotatedCandidate(
                    e, sources_from_kind(e.kind), evidence_for_detector_kind(e.kind)
                )
            )
        else:
            e2 = EngineCandidate(
                candidate_id=e.candidate_id,
                rule_id=e.rule_id,
                proposed_wrong=e.proposed_wrong,
                proposed_right=e.proposed_right,
                kind=e.kind,
                confidence=ranking_confidence_from_evidence(ann.evidence),
                occurrences=e.occurrences,
            )
            final.append(AnnotatedCandidate(e2, ann.sources, ann.evidence))
    return final, conflicts
