"""CorrectionsStudioPreviewService: compile_studio_to_engine_apply + engine preview (no snapshot writes)."""

from __future__ import annotations

import copy
from typing import Any, Dict

from transcriptx.core.corrections.apply import apply_corrections
from transcriptx.core.corrections.memory import load_memory
from transcriptx.core.corrections.models import CorrectionRule
from transcriptx.core.utils.canonicalization import compute_transcript_identity_hash
from transcriptx.core.store.corrections_session_store import session_path_for_transcript
from transcriptx.io import load_segments
from transcriptx.services.corrections_studio.compile import (
    compile_studio_to_engine_apply,
)
from transcriptx.services.corrections_studio.session_service import (
    CorrectionsStudioSessionService,
)


class CorrectionsStudioPreviewService:
    def __init__(self, session_service: CorrectionsStudioSessionService) -> None:
        self._session = session_service

    def compute_preview(self, session_id: str) -> Dict[str, Any]:
        doc = self._session.load_document(session_id)
        transcript_path = doc.transcript_path
        segments = load_segments(transcript_path)
        transcript_key = compute_transcript_identity_hash(segments)

        memory = load_memory(
            transcript_path=transcript_path,
            transcript_decisions_path=str(session_path_for_transcript(transcript_path)),
        )
        rules_by_id: Dict[str, CorrectionRule] = {}
        for rule in memory.rules.values():
            if rule.id:
                rules_by_id[rule.id] = rule

        compiled = compile_studio_to_engine_apply(
            session=doc,
            segments=segments,
            transcript_key=transcript_key,
            rules_by_id=rules_by_id,
        )
        rules_by_id.update(compiled.rules_by_id)

        for dec in compiled.engine_decisions:
            if dec.new_rule and dec.new_rule.id:
                rules_by_id[dec.new_rule.id] = dec.new_rule

        preview_segments = copy.deepcopy(segments)
        updated_segments, patch_log = apply_corrections(
            segments=preview_segments,
            candidates=compiled.engine_candidates,
            transcript_key=transcript_key,
            decisions=compiled.engine_decisions,
            rules_by_id=rules_by_id,
        )

        applied = sum(
            1
            for e in patch_log
            if "resolution_policy" not in e
            and e.get("status") not in ("conflict_skipped", "skipped_no_span")
        )

        cur = doc.current_generation_id
        if cur is None:
            accept_n = 0
        else:
            accepted_ids = {
                r.candidate_id
                for r in doc.review_records
                if r.generation_id == cur
                and r.review_action.value in ("accept", "learn")
            }
            accept_n = len(accepted_ids)

        return {
            "updated_segments": updated_segments,
            "patch_log": patch_log,
            "stats": {
                "applied_count": applied,
                "total_accepted": accept_n,
            },
        }
