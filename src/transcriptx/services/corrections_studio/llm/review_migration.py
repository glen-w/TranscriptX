"""Safe review migration plan for regeneration (events are authoritative)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from transcriptx.services.corrections_studio.review_target import (
    normalize_review_target_text,
)
from transcriptx.services.corrections_studio.schema import (
    ApplyScope,
    ReviewAction,
    ReviewMigrationSummary,
    ReviewRecordedPayload,
    StudioCandidate,
    StudioReviewRecord,
    StudioRule,
)

_CARRY_ACTIONS = {ReviewAction.accept, ReviewAction.reject, ReviewAction.learn}


def _occ_keyset(c: StudioCandidate) -> Set[str]:
    return {o.stable_occurrence_key for o in c.occurrences if o.stable_occurrence_key}


def _occ_span_map(c: StudioCandidate) -> Dict[str, Tuple[str, Optional[tuple]]]:
    return {
        o.stable_occurrence_key: (o.segment_id, o.span)
        for o in c.occurrences
        if o.stable_occurrence_key
    }


@dataclass
class MigrationPlan:
    reviews: List[ReviewRecordedPayload]
    summary: ReviewMigrationSummary


def build_review_migration_plan(
    *,
    prior_candidates: List[StudioCandidate],
    prior_reviews: List[StudioReviewRecord],
    new_candidates: List[StudioCandidate],
    prior_generation_id: Optional[int],
    new_generation_id: int,
    rules_by_id: Optional[Dict[str, StudioRule]] = None,
) -> MigrationPlan:
    if prior_generation_id is None:
        return MigrationPlan(
            reviews=[],
            summary=ReviewMigrationSummary(),
        )

    rules_by_id = rules_by_id or {}
    prior_by_sem: Dict[str, StudioCandidate] = {}
    for c in prior_candidates:
        if c.generation_id != prior_generation_id:
            continue
        if c.semantic_identity_key:
            prior_by_sem[c.semantic_identity_key] = c

    latest: Dict[str, StudioReviewRecord] = {}
    for r in sorted(
        [x for x in prior_reviews if x.generation_id == prior_generation_id],
        key=lambda x: x.event_sequence,
    ):
        latest[r.candidate_id] = r

    review_by_cand = latest
    carried = 0
    reset = 0
    orphaned = 0
    out: List[ReviewRecordedPayload] = []

    matched_prior_ids: Set[str] = set()

    for new_c in new_candidates:
        sem = new_c.semantic_identity_key
        if not sem or sem not in prior_by_sem:
            continue
        prior_c = prior_by_sem[sem]
        prior_rev = review_by_cand.get(prior_c.candidate_id)
        if prior_rev is None:
            continue
        matched_prior_ids.add(prior_c.candidate_id)
        if prior_rev.review_action not in _CARRY_ACTIONS:
            reset += 1
            continue

        prior_keys = _occ_keyset(prior_c)
        new_keys = _occ_keyset(new_c)
        prior_spans = _occ_span_map(prior_c)
        new_spans = _occ_span_map(new_c)

        scope = prior_rev.apply_scope
        selected = list(prior_rev.selected_occurrence_keys)

        if scope == ApplyScope.all:
            # Exact occurrence-set equality required
            if prior_keys != new_keys:
                reset += 1
                continue
            # Also require same segment+span for each key
            if any(prior_spans.get(k) != new_spans.get(k) for k in prior_keys):
                reset += 1
                continue
            selected = []
        else:
            surviving = []
            for k in selected:
                if k in new_spans and prior_spans.get(k) == new_spans.get(k):
                    surviving.append(k)
            if not surviving:
                reset += 1
                continue
            selected = surviving
            scope = ApplyScope.selected

        target = normalize_review_target_text(prior_rev.review_target_text)
        if prior_rev.review_target_text is not None:
            wrong_n = normalize_review_target_text(new_c.wrong_text) or ""
            # Edited override must remain non-empty and actually change the source.
            if target is None or not target.strip() or target == wrong_n:
                reset += 1
                continue

        if prior_rev.review_action == ReviewAction.learn:
            rule_id = prior_rev.learn_rule_id
            if not rule_id or rule_id not in rules_by_id:
                reset += 1
                continue

        out.append(
            ReviewRecordedPayload(
                generation_id=new_generation_id,
                candidate_id=new_c.candidate_id,
                review_action=prior_rev.review_action,
                apply_scope=scope,
                selected_occurrence_keys=selected,
                learn_intent=prior_rev.learn_intent,
                learn_rule_id=prior_rev.learn_rule_id,
                review_target_text=target,
                migrated_from_generation_id=prior_generation_id,
            )
        )
        carried += 1

    for cid, rev in review_by_cand.items():
        if cid not in matched_prior_ids and rev.review_action in _CARRY_ACTIONS:
            orphaned += 1

    return MigrationPlan(
        reviews=out,
        summary=ReviewMigrationSummary(
            carried=carried, reset=reset, orphaned_prior=orphaned
        ),
    )
