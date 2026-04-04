"""
Single compile entry: studio snapshot → engine apply_corrections inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from transcriptx.core.corrections.models import (
    Candidate,
    CorrectionRule,
    Decision,
    Occurrence,
)
from transcriptx.services.corrections_studio.schema import (
    ApplyScope,
    ReviewAction,
    StudioCandidate,
    StudioReviewRecord,
    StudioRule,
    StudioSessionDocument,
)


@dataclass
class CompiledStudioApply:
    """Engine inputs produced from a studio session (current generation only)."""

    engine_candidates: List[Candidate]
    engine_decisions: List[Decision]
    rules_by_id: Dict[str, CorrectionRule]


def _coerce_engine_rule_type(rule_type: str) -> str:
    if rule_type in ("token", "phrase", "acronym", "regex"):
        return rule_type
    return "phrase"


def _studio_rule_to_engine(rule: StudioRule) -> CorrectionRule:
    from transcriptx.core.corrections.models import CorrectionConditions

    conditions = None
    if rule.conditions_json:
        conditions = CorrectionConditions(**rule.conditions_json)
    return CorrectionRule(
        id=rule.rule_id,
        type=_coerce_engine_rule_type(rule.rule_type),  # type: ignore[arg-type]
        wrong=list(rule.wrong_variants),
        right=rule.replacement_text,
        scope=rule.scope,  # type: ignore[arg-type]
        confidence=rule.confidence,
        auto_apply=rule.auto_apply,
        conditions=conditions,
        is_person_name=rule.is_person_name,
    )


def _coerce_engine_kind(kind: str) -> str:
    valid = ("memory_hit", "acronym", "consistency", "fuzzy", "ner_variant")
    return kind if kind in valid else "consistency"


def _studio_candidate_to_engine(sc: StudioCandidate) -> Candidate:
    occs = []
    for o in sc.occurrences:
        span_t: Optional[Tuple[int, int]] = o.span
        occs.append(
            Occurrence(
                segment_id=o.segment_id,
                speaker=o.speaker,
                time_start=o.time_start,
                time_end=o.time_end,
                span=span_t,
                snippet=o.snippet or "",
                occurrence_id=o.stable_occurrence_key,
            )
        )
    return Candidate(
        candidate_id=sc.candidate_id,
        rule_id=sc.rule_id,
        proposed_wrong=sc.wrong_text,
        proposed_right=sc.right_text,
        kind=_coerce_engine_kind(sc.kind),  # type: ignore[arg-type]
        confidence=sc.confidence,
        occurrences=occs,
    )


def compile_studio_to_engine_apply(
    *,
    session: StudioSessionDocument,
    segments: List[Dict[str, Any]],  # reserved for future span validation
    transcript_key: str,
    rules_by_id: Optional[Dict[str, CorrectionRule]] = None,
    generation_id: Optional[int] = None,
) -> CompiledStudioApply:
    """
    Map studio review state + candidates for one generation to engine Candidate/Decision lists.

    Ignores review_records where generation_id < target generation.
    Accept / learn with apply selected → apply_some + occurrence keys; accept all → apply_all.
    """
    _ = segments  # reserved for compile-time validation against transcript
    gen = generation_id if generation_id is not None else session.current_generation_id
    if gen is None:
        return CompiledStudioApply(
            engine_candidates=[], engine_decisions=[], rules_by_id={}
        )

    rules = dict(rules_by_id or {})
    for sr in session.rules.values():
        er = _studio_rule_to_engine(sr)
        if er.id:
            rules[er.id] = er

    candidates_cur = [c for c in session.candidates if c.generation_id == gen]
    by_id = {c.candidate_id: c for c in candidates_cur}

    reviews_cur = [r for r in session.review_records if r.generation_id == gen]
    latest_by_candidate: Dict[str, StudioReviewRecord] = {}
    for r in sorted(reviews_cur, key=lambda x: x.event_sequence):
        latest_by_candidate[r.candidate_id] = r

    engine_candidates: List[Candidate] = []
    engine_decisions: List[Decision] = []

    for cand_id, rec in latest_by_candidate.items():
        if rec.review_action in (ReviewAction.reject, ReviewAction.skip):
            continue
        if rec.review_action not in (ReviewAction.accept, ReviewAction.learn):
            continue
        sc = by_id.get(cand_id)
        if not sc:
            continue
        engine_candidates.append(_studio_candidate_to_engine(sc))

        new_rule = None
        if (
            rec.review_action == ReviewAction.learn
            and rec.learn_rule_id
            and rec.learn_rule_id in session.rules
        ):
            new_rule = _studio_rule_to_engine(session.rules[rec.learn_rule_id])

        if rec.apply_scope == ApplyScope.selected and rec.selected_occurrence_keys:
            engine_decisions.append(
                Decision(
                    candidate_id=cand_id,
                    decision="apply_some",
                    selected_occurrence_ids=list(rec.selected_occurrence_keys),
                    new_rule=new_rule,
                )
            )
        else:
            engine_decisions.append(
                Decision(
                    candidate_id=cand_id,
                    decision="apply_all",
                    new_rule=new_rule,
                )
            )

    return CompiledStudioApply(
        engine_candidates=engine_candidates,
        engine_decisions=engine_decisions,
        rules_by_id=rules,
    )
