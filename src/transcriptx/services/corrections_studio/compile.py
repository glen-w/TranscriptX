"""
Single compile entry: studio snapshot → engine apply_corrections inputs.

Every accepted occurrence is re-grounded against live segment text before apply.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from transcriptx.core.corrections.detect import resolve_segment_id
from transcriptx.core.corrections.models import (
    Candidate,
    CorrectionRule,
    Decision,
    Occurrence,
)
from transcriptx.services.corrections_studio.review_target import (
    normalize_review_target_text,
    resolve_effective_right,
)
from transcriptx.services.corrections_studio.schema import (
    ApplyScope,
    ReviewAction,
    StudioOccurrence,
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
    compile_diagnostics: Dict[str, Any] = field(default_factory=dict)


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
    valid = (
        "memory_hit",
        "acronym",
        "consistency",
        "fuzzy",
        "ner_variant",
        "manual",
    )
    return kind if kind in valid else "consistency"


def _segment_text_by_id(
    segments: List[Dict[str, Any]], transcript_key: str
) -> Dict[str, Tuple[int, str]]:
    out: Dict[str, Tuple[int, str]] = {}
    for i, seg in enumerate(segments):
        sid = resolve_segment_id(seg, transcript_key, segment_index=i)
        out[sid] = (i, str(seg.get("text") or ""))
    return out


def _reground_occurrence(
    occ: StudioOccurrence,
    *,
    wrong_text: str,
    seg_map: Dict[str, Tuple[int, str]],
) -> Optional[StudioOccurrence]:
    found = seg_map.get(occ.segment_id)
    if found is None:
        return None
    _idx, text = found
    span = occ.span
    if span is None or len(span) != 2:
        return None
    start, end = int(span[0]), int(span[1])
    if start < 0 or end > len(text) or start >= end:
        return None
    if text[start:end] != wrong_text:
        return None
    return occ


def compile_studio_to_engine_apply(
    *,
    session: StudioSessionDocument,
    segments: List[Dict[str, Any]],
    transcript_key: str,
    rules_by_id: Optional[Dict[str, CorrectionRule]] = None,
    generation_id: Optional[int] = None,
    candidate_ids: Optional[List[str]] = None,
    occurrence_keys: Optional[List[str]] = None,
) -> CompiledStudioApply:
    """
    Map studio review state + candidates for one generation to engine Candidate/Decision lists.

    Re-grounds every accepted occurrence against live transcript text (fail closed).

    When ``candidate_ids`` is provided, only those candidates are compiled (scoped apply).
    When ``occurrence_keys`` is also provided, apply_scope is forced to selected for those keys.
    """
    gen = generation_id if generation_id is not None else session.current_generation_id
    diag: Dict[str, Any] = {
        "dropped_occurrences": 0,
        "dropped_candidates": 0,
        "invalid_targets": 0,
    }
    if gen is None:
        return CompiledStudioApply(
            engine_candidates=[],
            engine_decisions=[],
            rules_by_id={},
            compile_diagnostics=diag,
        )

    rules = dict(rules_by_id or {})
    for sr in session.rules.values():
        er = _studio_rule_to_engine(sr)
        if er.id:
            rules[er.id] = er

    candidates_cur = [c for c in session.candidates if c.generation_id == gen]
    if candidate_ids is not None:
        wanted = set(candidate_ids)
        candidates_cur = [c for c in candidates_cur if c.candidate_id in wanted]
    by_id = {c.candidate_id: c for c in candidates_cur}

    reviews_cur = [r for r in session.review_records if r.generation_id == gen]
    latest_by_candidate: Dict[str, StudioReviewRecord] = {}
    for r in sorted(reviews_cur, key=lambda x: x.event_sequence):
        latest_by_candidate[r.candidate_id] = r

    # Scoped apply: only compile the requested candidates (even if others accepted).
    if candidate_ids is not None:
        latest_by_candidate = {
            cid: rec
            for cid, rec in latest_by_candidate.items()
            if cid in set(candidate_ids)
        }

    seg_map = _segment_text_by_id(segments, transcript_key)
    engine_candidates: List[Candidate] = []
    engine_decisions: List[Decision] = []

    for cand_id, rec in latest_by_candidate.items():
        if rec.review_action in (ReviewAction.reject, ReviewAction.skip):
            continue
        if rec.review_action not in (ReviewAction.accept, ReviewAction.learn):
            continue
        sc = by_id.get(cand_id)
        if not sc:
            diag["dropped_candidates"] += 1
            continue
        proposed_right = resolve_effective_right(
            candidate_right_text=sc.right_text,
            review_target_normalized=normalize_review_target_text(
                rec.review_target_text
            ),
        )
        if normalize_review_target_text(proposed_right) is None:
            proposed_right = sc.right_text
        if not proposed_right or proposed_right == sc.wrong_text:
            diag["invalid_targets"] += 1
            diag["dropped_candidates"] += 1
            continue

        valid_occs: List[StudioOccurrence] = []
        if not segments:
            # No live transcript in this call — trust stored occurrences (unit fixtures).
            valid_occs = list(sc.occurrences)
        elif sc.occurrences:
            for occ in sc.occurrences:
                grounded = _reground_occurrence(
                    occ, wrong_text=sc.wrong_text, seg_map=seg_map
                )
                if grounded is None:
                    diag["dropped_occurrences"] += 1
                    continue
                valid_occs.append(grounded)
            if not valid_occs:
                diag["dropped_candidates"] += 1
                continue
        # Empty occurrence lists with live segments still compile (legacy).

        valid_keys = {
            o.stable_occurrence_key for o in valid_occs if o.stable_occurrence_key
        }
        selected_keys = [
            k
            for k in rec.selected_occurrence_keys
            if (not valid_keys) or k in valid_keys
        ]
        apply_scope = rec.apply_scope
        if occurrence_keys is not None and candidate_ids is not None:
            # Scoped occurrence subset for viewer quick-apply.
            selected_keys = [
                k for k in occurrence_keys if (not valid_keys) or k in valid_keys
            ]
            apply_scope = ApplyScope.selected
            if occurrence_keys and not selected_keys and valid_keys:
                diag["dropped_candidates"] += 1
                continue

        if apply_scope == ApplyScope.selected:
            if (
                rec.selected_occurrence_keys
                and not selected_keys
                and valid_keys
                and occurrence_keys is None
            ):
                diag["dropped_candidates"] += 1
                continue
            if valid_keys:
                apply_occs = [
                    o for o in valid_occs if o.stable_occurrence_key in selected_keys
                ]
            else:
                apply_occs = valid_occs
                selected_keys = list(rec.selected_occurrence_keys)
        else:
            apply_occs = valid_occs

        eng_occs = []
        for o in apply_occs:
            eng_occs.append(
                Occurrence(
                    segment_id=o.segment_id,
                    speaker=o.speaker,
                    time_start=o.time_start,
                    time_end=o.time_end,
                    span=o.span,
                    snippet=o.snippet or "",
                    occurrence_id=o.stable_occurrence_key,
                )
            )
        engine_candidates.append(
            Candidate(
                candidate_id=sc.candidate_id,
                rule_id=sc.rule_id,
                proposed_wrong=sc.wrong_text,
                proposed_right=proposed_right,
                kind=_coerce_engine_kind(sc.kind),  # type: ignore[arg-type]
                confidence=sc.confidence,
                occurrences=eng_occs,
            )
        )

        new_rule = None
        if (
            rec.review_action == ReviewAction.learn
            and rec.learn_rule_id
            and rec.learn_rule_id in session.rules
        ):
            new_rule = _studio_rule_to_engine(session.rules[rec.learn_rule_id])

        if apply_scope == ApplyScope.selected and selected_keys:
            engine_decisions.append(
                Decision(
                    candidate_id=cand_id,
                    decision="apply_some",
                    selected_occurrence_ids=list(selected_keys),
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
        compile_diagnostics=diag,
    )
