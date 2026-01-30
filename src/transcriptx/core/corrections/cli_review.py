from __future__ import annotations

from typing import List, Optional

from transcriptx.core.corrections.models import Candidate, CorrectionConditions, Decision, CorrectionRule
from transcriptx.utils.text_utils import format_time, is_named_speaker


def _format_time_window(start: Optional[float], end: Optional[float]) -> str:
    if start is None and end is None:
        return "?"
    if start is None:
        return f"?-{format_time(end)}"
    if end is None:
        return f"{format_time(start)}-?"
    return f"{format_time(start)}-{format_time(end)}"


def _print_occurrence_examples(candidate: Candidate, limit: int = 3) -> None:
    print(f"Occurrences: {len(candidate.occurrences)}")
    for occ in candidate.occurrences[:limit]:
        time_window = _format_time_window(occ.time_start, occ.time_end)
        speaker = occ.speaker or "UNKNOWN"
        print(f"- [{time_window}] {speaker}: {occ.snippet}")


def _prompt_action() -> str:
    while True:
        raw = input("Action [a/s/c/l/r/k]: ").strip().lower()
        if not raw:
            continue
        cmd = raw[0]
        if cmd in {"a", "s", "c", "l", "r", "k"}:
            return cmd


def _select_occurrences(candidate: Candidate) -> List[str]:
    for idx, occ in enumerate(candidate.occurrences, start=1):
        time_window = _format_time_window(occ.time_start, occ.time_end)
        speaker = occ.speaker or "UNKNOWN"
        print(f"{idx}. [{time_window}] {speaker}: {occ.snippet}")
    raw = input("Select occurrences (comma-separated indices): ").strip()
    indices = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            idx = int(part)
            if 1 <= idx <= len(candidate.occurrences):
                indices.append(idx)
        except ValueError:
            continue
    return [candidate.occurrences[i - 1].occurrence_id for i in indices]


def _prompt_conditions(candidate: Candidate) -> CorrectionConditions:
    conditions = CorrectionConditions()
    raw = input("Condition [s=speaker, w=context word, n=none]: ").strip().lower()
    if raw.startswith("s"):
        speaker = input("Speaker name: ").strip()
        if speaker:
            conditions.speaker = speaker
    elif raw.startswith("w"):
        context = input("Context word(s) (comma-separated): ").strip()
        if context:
            conditions.context_any = [w.strip() for w in context.split(",") if w.strip()]
    return conditions


def _build_rule_from_candidate(
    candidate: Candidate, scope: str, conditions: Optional[CorrectionConditions] = None
) -> CorrectionRule:
    # Set is_person_name for rules that introduce a person name (fuzzy speaker correction, or name capitalization)
    is_person_name = (
        candidate.kind == "fuzzy"
        or (
            candidate.kind in ("token", "phrase")
            and is_named_speaker(candidate.proposed_right)
        )
    )
    return CorrectionRule(
        type="phrase" if " " in candidate.proposed_wrong else "token",
        wrong=[candidate.proposed_wrong],
        right=candidate.proposed_right,
        scope=scope,
        confidence=candidate.confidence,
        auto_apply=False,
        conditions=conditions,
        is_person_name=is_person_name,
    )


def review_candidates(
    candidates: List[Candidate],
    default_rule_scope: str = "project",
) -> List[Decision]:
    decisions: List[Decision] = []
    candidates = sorted(candidates, key=lambda c: c.confidence, reverse=True)
    for candidate in candidates:
        print("\n---")
        print(
            f"Suggest: '{candidate.proposed_wrong}' → '{candidate.proposed_right}' "
            f"(kind={candidate.kind}, confidence={candidate.confidence:.2f})"
        )
        _print_occurrence_examples(candidate)
        action = _prompt_action()

        if action == "k":
            decisions.append(
                Decision(candidate_id=candidate.candidate_id, decision="skip")
            )
            continue
        if action == "r":
            decisions.append(
                Decision(candidate_id=candidate.candidate_id, decision="reject")
            )
            continue
        if action == "a":
            decisions.append(
                Decision(candidate_id=candidate.candidate_id, decision="apply_all")
            )
            continue
        if action == "s":
            selected = _select_occurrences(candidate)
            decisions.append(
                Decision(
                    candidate_id=candidate.candidate_id,
                    decision="apply_some",
                    selected_occurrence_ids=selected,
                )
            )
            continue
        if action == "c":
            conditions = _prompt_conditions(candidate)
            rule = _build_rule_from_candidate(
                candidate, scope=default_rule_scope, conditions=conditions
            )
            decisions.append(
                Decision(
                    candidate_id=candidate.candidate_id,
                    decision="apply_all",
                    new_rule=rule,
                )
            )
            continue
        if action == "l":
            rule = _build_rule_from_candidate(
                candidate, scope=default_rule_scope, conditions=None
            )
            decisions.append(
                Decision(
                    candidate_id=candidate.candidate_id,
                    decision="apply_all",
                    new_rule=rule,
                )
            )
            continue

    return decisions
