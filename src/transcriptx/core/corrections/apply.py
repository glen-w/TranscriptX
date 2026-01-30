from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from transcriptx.core.corrections.detect import resolve_segment_id
from transcriptx.core.corrections.models import Candidate, CorrectionRule, Decision
from transcriptx.utils.text_utils import is_named_speaker


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _is_unidentified_speaker(speaker: Optional[str]) -> bool:
    if not speaker:
        return True
    if speaker.upper().startswith("SPEAKER_"):
        return True
    if "UNKNOWN" in speaker.upper():
        return True
    return not is_named_speaker(speaker)


@dataclass
class PlannedReplacement:
    segment_index: int
    segment_id: str
    candidate_id: str
    rule_id: Optional[str]
    kind: str
    confidence: float
    wrong: str
    right: str
    span: Tuple[int, int]


def _candidate_priority(kind: str) -> int:
    priority = {"memory_hit": 3, "acronym": 2, "consistency": 1, "fuzzy": 0}
    return priority.get(kind, 0)


def _context_any_matches(segment_text: str, context_any: List[str], case_sensitive: bool, word_boundary: bool) -> bool:
    """Return True if segment_text contains at least one of the context terms."""
    if not context_any:
        return True
    text = segment_text or ""
    for term in context_any:
        term = term.strip()
        if not term:
            continue
        escaped = re.escape(term)
        if not case_sensitive:
            text_check = text.lower()
            term_check = term.lower()
        else:
            text_check = text
            term_check = term
        if word_boundary:
            # Boundaries: not alnum/underscore (works for multi-word and punctuation)
            pattern = rf"(?:^|[^A-Za-z0-9_]){escaped}(?:$|[^A-Za-z0-9_])"
            flags = 0 if case_sensitive else re.IGNORECASE
            if re.search(pattern, text, flags=flags):
                return True
        else:
            if term_check in text_check:
                return True
    return False


def _should_apply_to_segment(
    segment: Dict,
    rule: Optional[CorrectionRule],
) -> bool:
    if rule is None or rule.conditions is None:
        return True
    conditions = rule.conditions
    speaker = segment.get("speaker")
    if conditions.speaker and speaker != conditions.speaker:
        return False
    if conditions.min_token_len is not None:
        if len((segment.get("text") or "").split()) < conditions.min_token_len:
            return False
    if conditions.context_any:
        segment_text = segment.get("text") or ""
        if not _context_any_matches(
            segment_text,
            conditions.context_any,
            case_sensitive=conditions.case_sensitive,
            word_boundary=conditions.word_boundary,
        ):
            return False
    return True


def _resolve_decision_applications(
    candidates: Iterable[Candidate],
    decisions: Optional[Iterable[Decision]],
) -> Dict[str, Optional[List[str]]]:
    if not decisions:
        return {}
    decision_map: Dict[str, Optional[List[str]]] = {}
    for decision in decisions:
        if decision.decision == "apply_all":
            decision_map[decision.candidate_id] = None
        elif decision.decision == "apply_some":
            decision_map[decision.candidate_id] = decision.selected_occurrence_ids or []
    return decision_map


def apply_corrections(
    segments: List[Dict],
    candidates: List[Candidate],
    transcript_key: str,
    decisions: Optional[List[Decision]] = None,
    rules_by_id: Optional[Dict[str, CorrectionRule]] = None,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Apply corrections to segments and return (segments, patch_log_entries).
    """
    decision_map = _resolve_decision_applications(candidates, decisions)
    rules_by_id = rules_by_id or {}
    patch_log: List[Dict] = [{"resolution_policy": "longest_span > confidence > kind_priority > left_to_right"}]

    planned: List[PlannedReplacement] = []
    for idx, segment in enumerate(segments):
        text = segment.get("text", "")
        segment_id = resolve_segment_id(segment, transcript_key, segment_index=idx)
        for candidate in candidates:
            if decisions is not None and candidate.candidate_id not in decision_map:
                continue

            allowed_occurrence_ids = decision_map.get(candidate.candidate_id)
            rule = rules_by_id.get(candidate.rule_id) if candidate.rule_id else None
            if rule and not _should_apply_to_segment(segment, rule):
                continue

            for occ in candidate.occurrences:
                if occ.segment_id != segment_id:
                    continue
                if allowed_occurrence_ids is not None:
                    if occ.occurrence_id in allowed_occurrence_ids:
                        pass
                    elif occ.span and (
                        text[occ.span[0] : occ.span[1]] == candidate.proposed_wrong
                    ):
                        # Replay fallback: match by (segment_id, span, wrong) when occurrence_id missing
                        pass
                    else:
                        continue
                if occ.span is None:
                    # apply_some: span required; skip and log. apply_all: find all matches via finditer.
                    if allowed_occurrence_ids is not None:
                        # apply_some: cannot apply without span; log skipped_no_span
                        patch_log.append(
                            {
                                "timestamp": _now_iso(),
                                "rule_id": candidate.rule_id,
                                "candidate_id": candidate.candidate_id,
                                "segment_id": segment_id,
                                "speaker": segment.get("speaker"),
                                "time_start": segment.get("start", segment.get("start_time")),
                                "time_end": segment.get("end", segment.get("end_time")),
                                "before": text,
                                "after": text,
                                "status": "skipped_no_span",
                                "reason": "occurrence has no span; apply_some requires span",
                            }
                        )
                        continue
                    # apply_all: find all matches of proposed_wrong in segment
                    wrong_escaped = re.escape(candidate.proposed_wrong)
                    for m in re.finditer(wrong_escaped, text):
                        span = (m.start(), m.end())
                        planned.append(
                            PlannedReplacement(
                                segment_index=idx,
                                segment_id=segment_id,
                                candidate_id=candidate.candidate_id,
                                rule_id=candidate.rule_id,
                                kind=candidate.kind,
                                confidence=candidate.confidence,
                                wrong=candidate.proposed_wrong,
                                right=candidate.proposed_right,
                                span=span,
                            )
                        )
                    continue
                span = occ.span

                planned.append(
                    PlannedReplacement(
                        segment_index=idx,
                        segment_id=segment_id,
                        candidate_id=candidate.candidate_id,
                        rule_id=candidate.rule_id,
                        kind=candidate.kind,
                        confidence=candidate.confidence,
                        wrong=candidate.proposed_wrong,
                        right=candidate.proposed_right,
                        span=span,
                    )
                )

    replacements_by_segment: Dict[int, List[PlannedReplacement]] = {}
    for replacement in planned:
        replacements_by_segment.setdefault(replacement.segment_index, []).append(
            replacement
        )

    for segment_index, replacements in replacements_by_segment.items():
        segment = segments[segment_index]
        speaker = segment.get("speaker")
        if _is_unidentified_speaker(speaker):
            # Skip person-name corrections for unidentified speakers unless explicit rules
            filtered: List[PlannedReplacement] = []
            for rep in replacements:
                rule = rules_by_id.get(rep.rule_id) if rep.rule_id else None
                # Use is_person_name when set; fallback to is_named_speaker(right) for old rules
                is_person_rule = False
                if rule:
                    is_person_rule = getattr(rule, "is_person_name", False)
                    if not is_person_rule and rule.type in ("token", "phrase"):
                        is_person_rule = is_named_speaker(rule.right)
                if is_person_rule:
                    continue
                if rep.kind in ("consistency", "fuzzy") and rule is None:
                    continue
                filtered.append(rep)
            replacements = filtered
        if not replacements:
            continue

        # Preserve raw text before any edits
        if "text_raw" not in segment:
            segment["text_raw"] = segment.get("text", "")

        text_before = segment.get("text", "")
        replacements.sort(
            key=lambda rep: (
                -(rep.span[1] - rep.span[0]),
                -rep.confidence,
                -_candidate_priority(rep.kind),
                rep.span[0],
            )
        )

        selected: List[PlannedReplacement] = []
        occupied: List[Tuple[Tuple[int, int], PlannedReplacement]] = []
        for rep in replacements:
            overlapping = [
                orep
                for (ospan, orep) in occupied
                if not (rep.span[1] <= ospan[0] or rep.span[0] >= ospan[1])
            ]
            if overlapping:
                patch_log.append(
                    {
                        "timestamp": _now_iso(),
                        "rule_id": rep.rule_id,
                        "candidate_id": rep.candidate_id,
                        "segment_id": rep.segment_id,
                        "speaker": speaker,
                        "time_start": segment.get("start", segment.get("start_time")),
                        "time_end": segment.get("end", segment.get("end_time")),
                        "before": text_before,
                        "after": text_before,
                        "status": "conflict_skipped",
                        "conflicts_with": [
                            {
                                "span": orep.span,
                                "candidate_id": orep.candidate_id,
                                "rule_id": orep.rule_id,
                                "kind": orep.kind,
                                "confidence": orep.confidence,
                            }
                            for orep in overlapping
                        ],
                        "replacements": [
                            {
                                "wrong": rep.wrong,
                                "right": rep.right,
                                "span_before": rep.span,
                                "span_after": None,
                            }
                        ],
                    }
                )
                continue
            selected.append(rep)
            occupied.append((rep.span, rep))

        if not selected:
            continue

        # Apply replacements from right to left
        selected.sort(key=lambda rep: rep.span[0], reverse=True)
        updated_text = text_before
        applied_replacements: List[Dict] = []
        for rep in selected:
            start, end = rep.span
            updated_text = updated_text[:start] + rep.right + updated_text[end:]
            applied_replacements.append(
                {
                    "wrong": rep.wrong,
                    "right": rep.right,
                    "span_before": (start, end),
                    "span_after": (start, start + len(rep.right)),
                }
            )

        segment["text"] = updated_text
        patch_log.append(
            {
                "timestamp": _now_iso(),
                "rule_id": selected[0].rule_id,
                "candidate_id": selected[0].candidate_id,
                "segment_id": selected[0].segment_id,
                "speaker": speaker,
                "time_start": segment.get("start", segment.get("start_time")),
                "time_end": segment.get("end", segment.get("end_time")),
                "before": text_before,
                "after": updated_text,
                "replacements": applied_replacements,
            }
        )

    return segments, patch_log
