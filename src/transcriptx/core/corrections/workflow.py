from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from transcriptx.core.corrections.apply import apply_corrections
from transcriptx.core.corrections.cli_review import review_candidates
from transcriptx.core.corrections.detect import (
    detect_acronym_candidates,
    detect_consistency_candidates,
    detect_fuzzy_candidates,
    detect_memory_hits,
)
from transcriptx.core.corrections.memory import load_memory, promote_rule
from transcriptx.core.corrections.models import Candidate, CorrectionRule, Decision, Occurrence
from transcriptx.core.utils.canonicalization import compute_transcript_identity_hash
from transcriptx.core.output.output_service import create_output_service
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.speaker_extraction import (
    get_unique_speakers,
    set_speaker_display_map,
)
from transcriptx.io import load_segments, load_transcript, save_json
from transcriptx.io.transcript_loader import extract_speaker_map_from_transcript

logger = get_logger()


def _derive_speaker_map(
    segments: List[Dict[str, Any]], transcript_path: str
) -> Dict[Any, str]:
    speaker_map_metadata = extract_speaker_map_from_transcript(transcript_path)
    if speaker_map_metadata:
        set_speaker_display_map(speaker_map_metadata)
    return cast(Dict[Any, str], get_unique_speakers(segments))


def _rule_signature_for_dedupe(rule: Optional[CorrectionRule]) -> tuple:
    """Return (conditions_signature, speaker) for dedupe key; rules with different conditions stay separate."""
    if not rule or not rule.conditions:
        return (None, None)
    cond = rule.conditions
    cond_sig = (
        cond.speaker,
        cond.min_token_len,
        tuple(sorted(cond.context_any or [])),
        cond.case_sensitive,
        cond.word_boundary,
    )
    return (cond_sig, cond.speaker)


def _dedupe_candidates(
    candidates: List[Candidate],
    rules_by_id: Optional[Dict[str, CorrectionRule]] = None,
) -> List[Candidate]:
    """Merge duplicate candidates (same kind, wrong, right, conditions); keep max confidence, merge occurrences."""
    rules_by_id = rules_by_id or {}
    key_to_candidate: Dict[tuple, Candidate] = {}
    for c in candidates:
        rule = rules_by_id.get(c.rule_id) if c.rule_id else None
        cond_sig, _ = _rule_signature_for_dedupe(rule)
        key = (c.kind, c.proposed_wrong.lower(), c.proposed_right.lower(), cond_sig)
        existing = key_to_candidate.get(key)
        if existing is None:
            key_to_candidate[key] = c
            continue
        # Merge: keep higher confidence, merge occurrences (dedupe by segment_id + span)
        best_conf = max(existing.confidence, c.confidence)
        seen: set = set()
        merged_occ: List[Occurrence] = []
        for occ in existing.occurrences + c.occurrences:
            span_key = (occ.segment_id, occ.span[0] if occ.span else None, occ.span[1] if occ.span else None)
            if span_key in seen:
                continue
            seen.add(span_key)
            merged_occ.append(occ)
        key_to_candidate[key] = Candidate(
            candidate_id=existing.candidate_id,
            rule_id=existing.rule_id,
            proposed_wrong=existing.proposed_wrong,
            proposed_right=existing.proposed_right,
            kind=existing.kind,
            confidence=best_conf,
            occurrences=merged_occ,
        )
    return list(key_to_candidate.values())


def _backup_transcript_file(transcript_path: str) -> str:
    source = Path(transcript_path)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = source.with_suffix(f"{source.suffix}.backup_{timestamp}")
    shutil.copy2(source, backup_path)
    logger.info(f"Backed up transcript to: {backup_path}")
    return str(backup_path)


def _write_updated_transcript(
    transcript_path: str,
    updated_segments: List[Dict[str, Any]],
    create_backup: bool = True,
) -> str:
    if create_backup:
        _backup_transcript_file(transcript_path)

    transcript_data = load_transcript(transcript_path)
    if isinstance(transcript_data, dict):
        transcript_data["segments"] = updated_segments
        save_json(transcript_data, transcript_path)
    else:
        save_json(updated_segments, transcript_path)
    logger.info(f"Updated transcript file: {transcript_path}")
    return transcript_path


def run_corrections_on_segments(
    *,
    segments: List[Dict[str, Any]],
    transcript_path: str,
    transcript_key: Optional[str] = None,
    speaker_map: Optional[Dict[Any, str]] = None,
    config: Optional[Any] = None,
    interactive_review: Optional[bool] = None,
    output_dir: Optional[str] = None,
    apply_changes: bool = True,
) -> Dict[str, Any]:
    config = config or get_config()
    corrections_config = getattr(config.analysis, "corrections", None)
    if corrections_config is None or not corrections_config.enabled:
        logger.info("Corrections module disabled in config.")
        return {"status": "skipped", "suggestions_count": 0, "applied_count": 0}

    if transcript_key is None:
        transcript_key = compute_transcript_identity_hash(segments)
    if speaker_map is None:
        speaker_map = _derive_speaker_map(segments, transcript_path)

    interactive_review = (
        corrections_config.interactive_review
        if interactive_review is None
        else interactive_review
    )

    output_service = create_output_service(
        transcript_path, "corrections", output_dir=output_dir
    )
    output_dir_path = output_service.get_output_structure().global_data_dir
    decisions_path = output_dir_path / f"{output_service.base_name}_corrections_decisions.json"

    memory = load_memory(
        transcript_path=transcript_path,
        transcript_decisions_path=str(decisions_path)
        if decisions_path.exists()
        else None,
    )

    candidates: List[Candidate] = []
    candidates.extend(detect_memory_hits(segments, transcript_key, memory.rules.values()))
    candidates.extend(
        detect_acronym_candidates(
            segments,
            transcript_key,
            corrections_config.known_acronyms,
            corrections_config.known_org_phrases,
        )
    )
    candidates.extend(
        detect_consistency_candidates(
            segments,
            transcript_key,
            corrections_config.consistency_similarity_threshold,
        )
    )
    candidates.extend(
        detect_fuzzy_candidates(
            segments,
            transcript_key,
            list(speaker_map.values()),
            corrections_config.fuzzy_similarity_threshold,
            getattr(corrections_config, "enable_fuzzy", False),
        )
    )

    candidates = _dedupe_candidates(candidates, rules_by_id=memory.rules)
    suggestions_payload = [candidate.model_dump() for candidate in candidates]
    suggestions_path = output_service.save_data(
        suggestions_payload, "corrections_suggestions", format_type="json"
    )

    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}

    decisions: Optional[List[Decision]] = None
    decisions_path_saved: Optional[str] = None
    if interactive_review:
        decisions = review_candidates(
            candidates, default_rule_scope=corrections_config.default_rule_scope
        )
        if decisions is not None:
            decisions_path_saved = output_service.save_data(
                [decision.model_dump() for decision in decisions],
                "corrections_decisions",
                format_type="json",
            )

    apply_candidates = candidates
    if not interactive_review:
        apply_candidates = [
            candidate
            for candidate in candidates
            if candidate.rule_id
            and memory.rules.get(candidate.rule_id)
            and memory.rules[candidate.rule_id].auto_apply
        ]

    updated_segments = segments
    patch_log: List[Dict[str, Any]] = []
    patch_log_path: Optional[str] = None
    corrected_transcript_path: Optional[str] = None
    if apply_changes and apply_candidates:
        updated_segments, patch_log = apply_corrections(
            segments=segments,
            candidates=apply_candidates,
            transcript_key=transcript_key,
            decisions=decisions,
            rules_by_id=memory.rules,
        )

    if apply_changes:
        patch_log_path = output_service.save_data(
            patch_log, "corrections_patch_log", format_type="json"
        )

    if decisions and apply_changes:
        for decision in decisions:
            if decision.new_rule:
                if decision.new_rule.scope in {"global", "project"}:
                    promote_rule(
                        decision.new_rule,
                        decision.new_rule.scope,
                        transcript_path=transcript_path,
                    )
            elif decision.decision in {"apply_all", "apply_some"}:
                candidate = candidate_by_id.get(decision.candidate_id)
                if candidate and candidate.rule_id:
                    rule = memory.rules.get(candidate.rule_id)
                    if rule:
                        rule.confidence = min(1.0, rule.confidence + 0.05)
                        promote_rule(rule, "project", transcript_path=transcript_path)

    if apply_changes and corrections_config.store_corrected_transcript and patch_log:
        corrected_transcript_path = output_service.save_data(
            {"segments": updated_segments},
            "corrections_transcript",
            format_type="json",
        )

    if apply_changes and corrections_config.write_csv_summary and patch_log:
        summary: Dict[str, int] = {}
        for entry in patch_log:
            if "resolution_policy" in entry:
                continue
            rule_id = entry.get("rule_id") or "unruled"
            summary[rule_id] = summary.get(rule_id, 0) + 1
        output_service.save_data(
            [{"rule_id": k, "count": v} for k, v in summary.items()],
            "corrections_summary",
            format_type="csv",
        )

    return {
        "status": "success" if apply_changes else "suggestions_only",
        "suggestions_count": len(candidates),
        "applied_count": sum(
            1
            for e in patch_log
            if "resolution_policy" not in e
            and e.get("status") not in ("conflict_skipped", "skipped_no_span")
        ),
        "updated_segments": updated_segments if apply_changes else None,
        "patch_log": patch_log,
        "artifacts": output_service.get_artifacts(),
        "suggestions_path": suggestions_path,
        "decisions_path": decisions_path_saved,
        "patch_log_path": patch_log_path,
        "corrected_transcript_path": corrected_transcript_path,
    }


def run_corrections_workflow(
    transcript_path: str,
    *,
    interactive: bool = True,
    update_original_file: Optional[bool] = None,
    create_backup: Optional[bool] = None,
    config: Optional[Any] = None,
    output_dir: Optional[str] = None,
    apply_changes: bool = True,
) -> Dict[str, Any]:
    config = config or get_config()
    corrections_config = getattr(config.analysis, "corrections", None)
    if corrections_config is None:
        logger.info("Corrections module missing in config.")
        return {"status": "skipped", "suggestions_count": 0, "applied_count": 0}

    if update_original_file is None:
        update_original_file = getattr(corrections_config, "update_original_file", False)
    if create_backup is None:
        create_backup = getattr(corrections_config, "create_backup", True)

    segments = load_segments(transcript_path)
    transcript_key = compute_transcript_identity_hash(segments)
    speaker_map = _derive_speaker_map(segments, transcript_path)

    results = run_corrections_on_segments(
        segments=segments,
        transcript_path=transcript_path,
        transcript_key=transcript_key,
        speaker_map=speaker_map,
        config=config,
        interactive_review=interactive,
        output_dir=output_dir,
        apply_changes=apply_changes,
    )

    if (
        apply_changes
        and update_original_file
        and results.get("status") == "success"
        and results.get("applied_count", 0) > 0
    ):
        updated_segments = results.get("updated_segments")
        if isinstance(updated_segments, list):
            _write_updated_transcript(
                transcript_path, updated_segments, create_backup=create_backup
            )

    return results


def write_corrected_transcript(
    *,
    transcript_path: str,
    updated_segments: Optional[List[Dict[str, Any]]],
    create_backup: bool = True,
) -> Optional[str]:
    if not updated_segments:
        return None
    backup_path: Optional[str] = None
    if create_backup:
        backup_path = _backup_transcript_file(transcript_path)

    transcript_data = load_transcript(transcript_path)
    if isinstance(transcript_data, dict):
        transcript_data["segments"] = updated_segments
        save_json(transcript_data, transcript_path)
    else:
        save_json(updated_segments, transcript_path)
    logger.info(f"Updated transcript file: {transcript_path}")
    return backup_path
