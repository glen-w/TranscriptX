"""
CorrectionService: core business logic for the Corrections Studio.

Bridges DB repositories and the existing corrections engine. Takes a
SQLAlchemy session in constructor. Never leaks ORM objects -- all returns
are dicts or plain Python objects safe for st.session_state.
"""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.corrections.apply import apply_corrections
from transcriptx.core.corrections.detect import (
    detect_acronym_candidates,
    detect_consistency_candidates,
    detect_fuzzy_candidates,
    detect_memory_hits,
    resolve_segment_id,
)
from transcriptx.core.corrections.models import (
    Candidate,
    CorrectionConditions,
    CorrectionRule,
    Decision,
    Occurrence,
)
from transcriptx.core.corrections.workflow import _dedupe_candidates
from transcriptx.core.utils.canonicalization import compute_transcript_identity_hash
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger
from transcriptx.database.repositories.corrections import CorrectionRepository
from transcriptx.database.repositories.pipeline import ArtifactIndexRepository
from transcriptx.database.models.pipeline import PipelineRun, ModuleRun
from transcriptx.io import load_segments, save_json

logger = get_logger()

CORRECTIONS_SCHEMA_VERSION = "1"


def normalize_transcript_path(path: str) -> str:
    return str(Path(path).expanduser().resolve())


def _stable_occurrence_key(
    segment_id: str, span_start: int, span_end: int, wrong_text: str
) -> str:
    signature = f"{segment_id}:{span_start}:{span_end}:{wrong_text}"
    return hashlib.sha1(signature.encode("utf-8")).hexdigest()


def _enrich_occurrences(
    occurrences: List[Dict[str, Any]],
    segments: List[Dict[str, Any]],
    transcript_key: str,
    wrong_text: str,
) -> List[Dict[str, Any]]:
    """Add stable_occurrence_key and segment_index to each occurrence dict."""
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
            # No span: use index so multiple span-less occurrences in same segment stay distinct
            span_start, span_end = -1, -1
        base_key = _stable_occurrence_key(
            occ_dict["segment_id"], span_start, span_end, wrong_text
        )
        if span is None:
            occ_dict["stable_occurrence_key"] = f"{base_key}_{idx}"
        else:
            occ_dict["stable_occurrence_key"] = base_key
        occ_dict["segment_index"] = seg_id_to_index.get(occ_dict["segment_id"], -1)
        enriched.append(occ_dict)
    return enriched


def _db_rule_to_engine_rule(rule_dict: Dict[str, Any]) -> CorrectionRule:
    conditions = None
    if rule_dict.get("conditions_json"):
        conditions = CorrectionConditions(**rule_dict["conditions_json"])
    return CorrectionRule(
        id=rule_dict["rule_hash"],
        type=rule_dict["rule_type"],
        wrong=rule_dict["wrong_variants_json"],
        right=rule_dict["replacement_text"],
        scope=rule_dict["scope"],
        confidence=rule_dict.get("confidence", 0.0),
        auto_apply=rule_dict.get("auto_apply", False),
        conditions=conditions,
        is_person_name=rule_dict.get("is_person_name", False),
    )


class CorrectionService:
    def __init__(self, db_session: Any):
        self.repo = CorrectionRepository(db_session)
        self.db_session = db_session

    def start_or_resume_session(self, transcript_path: str) -> Dict[str, Any]:
        normalized = normalize_transcript_path(transcript_path)
        segments = load_segments(normalized)
        fingerprint = compute_transcript_identity_hash(segments)

        existing = self.repo.find_active_session(normalized, fingerprint)
        if existing:
            # Signal if candidates were generated with an older detector version
            existing = dict(existing)
            existing["candidates_stale"] = (
                existing.get("detector_version") != CORRECTIONS_SCHEMA_VERSION
            )
            return existing

        # No matching session; abandon any other active session for this path (fingerprint changed)
        other = self.repo.find_active_session_by_path(normalized)
        if other:
            self.repo.update_session_status(other["id"], "abandoned")

        session = self.repo.create_session(
            transcript_path=normalized,
            source_fingerprint=fingerprint,
            detector_version=CORRECTIONS_SCHEMA_VERSION,
            status="active",
        )
        session = dict(session)
        session["candidates_stale"] = False
        return session

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return session dict with candidates_stale set from detector_version."""
        session = self.repo.get_session(session_id)
        if not session:
            return None
        session = dict(session)
        session["candidates_stale"] = (
            session.get("detector_version") != CORRECTIONS_SCHEMA_VERSION
        )
        return session

    def generate_candidates(
        self, session_id: str, force: bool = False
    ) -> List[Dict[str, Any]]:
        session = self.repo.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        existing = self.repo.list_candidates(session_id, limit=1)
        if existing and not force:
            return self.repo.list_candidates(session_id, limit=10000)

        if force:
            self.repo.delete_decisions_for_session(session_id)
            self.repo.delete_candidates_for_session(session_id)

        transcript_path = session["transcript_path"]
        segments = load_segments(transcript_path)
        transcript_key = compute_transcript_identity_hash(segments)

        config = get_config()
        corrections_config = getattr(config.analysis, "corrections", None)

        # Gather DB-stored rules for detection
        db_global_rules = self.repo.find_enabled_rules("global")
        db_transcript_rules = self.repo.find_enabled_rules(
            "transcript", transcript_path=transcript_path
        )
        engine_rules = [
            _db_rule_to_engine_rule(r) for r in db_global_rules + db_transcript_rules
        ]

        candidates: List[Candidate] = []
        candidates.extend(detect_memory_hits(segments, transcript_key, engine_rules))

        if corrections_config:
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
            speaker_names: List[str] = []
            candidates.extend(
                detect_fuzzy_candidates(
                    segments,
                    transcript_key,
                    speaker_names,
                    getattr(corrections_config, "fuzzy_similarity_threshold", 0.85),
                    getattr(corrections_config, "enable_fuzzy", False),
                )
            )

        rules_by_id = {r.id: r for r in engine_rules if r.id}
        candidates = _dedupe_candidates(candidates, rules_by_id=rules_by_id)

        rows: List[Dict[str, Any]] = []
        for c in candidates:
            occ_dicts = [occ.model_dump() for occ in c.occurrences]
            enriched = _enrich_occurrences(
                occ_dicts, segments, transcript_key, c.proposed_wrong
            )
            rows.append(
                {
                    "candidate_hash": c.candidate_id or "",
                    "kind": c.kind,
                    "wrong_text": c.proposed_wrong,
                    "suggested_text": c.proposed_right,
                    "confidence": c.confidence,
                    "rule_id": c.rule_id,
                    "occurrences_json": enriched,
                    "evidence_json": None,
                    "status": "pending",
                }
            )

        return self.repo.bulk_create_candidates(session_id, rows)

    def list_candidates(
        self,
        session_id: str,
        status_filter: Optional[str] = None,
        kind_filter: Optional[List[str]] = None,
        confidence_min: Optional[float] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return self.repo.list_candidates(
            session_id,
            status_filter=status_filter,
            kind_filter=kind_filter,
            confidence_min=confidence_min,
            offset=offset,
            limit=limit,
        )

    def count_candidates(
        self,
        session_id: str,
        status_filter: Optional[str] = None,
        kind_filter: Optional[List[str]] = None,
        confidence_min: Optional[float] = None,
    ) -> int:
        return self.repo.count_candidates(
            session_id,
            status_filter=status_filter,
            kind_filter=kind_filter,
            confidence_min=confidence_min,
        )

    def record_decision(
        self,
        session_id: str,
        candidate_id: str,
        decision: str,
        selected_occurrence_keys: Optional[List[str]] = None,
        learn_rule_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        created_rule_id = None
        if learn_rule_params:
            rule_dict = self.repo.create_rule(
                source_session_id=session_id,
                **learn_rule_params,
            )
            created_rule_id = rule_dict["id"]

        self.repo.upsert_decision(
            session_id,
            candidate_id,
            decision=decision,
            selected_occurrence_ids_json=selected_occurrence_keys,
            created_rule_id=created_rule_id,
        )

        status_map = {"accept": "accepted", "reject": "rejected", "skip": "skipped"}
        self.repo.update_candidate_status(
            candidate_id, status_map.get(decision, decision)
        )

    def compute_preview(self, session_id: str) -> Dict[str, Any]:
        session = self.repo.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        transcript_path = session["transcript_path"]
        segments = load_segments(transcript_path)
        transcript_key = compute_transcript_identity_hash(segments)

        all_decisions = self.repo.get_decisions_for_session(session_id)
        accept_decisions = [d for d in all_decisions if d["decision"] == "accept"]

        # Collect candidate IDs we need
        candidate_ids = {d["candidate_id"] for d in accept_decisions}
        all_candidates = self.repo.list_candidates(session_id, limit=10000)
        relevant_candidates = [c for c in all_candidates if c["id"] in candidate_ids]

        engine_candidates: List[Candidate] = []
        engine_decisions: List[Decision] = []

        # Build occurrence_id mapping: stable_key -> engine occurrence_id
        for cand_dict in relevant_candidates:
            occs = cand_dict["occurrences_json"] or []
            engine_occs = []
            stable_to_engine: Dict[str, str] = {}
            for occ_data in occs:
                engine_occ = Occurrence(
                    occurrence_id=occ_data.get("occurrence_id"),
                    segment_id=occ_data["segment_id"],
                    speaker=occ_data.get("speaker"),
                    time_start=occ_data.get("time_start"),
                    time_end=occ_data.get("time_end"),
                    span=occ_data.get("span"),
                    snippet=occ_data.get("snippet", ""),
                )
                engine_occs.append(engine_occ)
                sk = occ_data.get("stable_occurrence_key")
                if sk and engine_occ.occurrence_id:
                    stable_to_engine[sk] = engine_occ.occurrence_id

            engine_cand = Candidate(
                candidate_id=cand_dict["candidate_hash"],
                rule_id=cand_dict.get("rule_id"),
                proposed_wrong=cand_dict["wrong_text"],
                proposed_right=cand_dict["suggested_text"],
                kind=cand_dict["kind"],
                confidence=cand_dict.get("confidence", 0.0),
                occurrences=engine_occs,
            )
            engine_candidates.append(engine_cand)

            # Build engine decision for this candidate
            dec_data = next(
                (d for d in accept_decisions if d["candidate_id"] == cand_dict["id"]),
                None,
            )
            if dec_data:
                sel_keys = dec_data.get("selected_occurrence_ids_json")
                if sel_keys:
                    sel_ids = [stable_to_engine.get(k, k) for k in sel_keys]
                    engine_decisions.append(
                        Decision(
                            candidate_id=engine_cand.candidate_id,
                            decision="apply_some",
                            selected_occurrence_ids=sel_ids,
                        )
                    )
                else:
                    engine_decisions.append(
                        Decision(
                            candidate_id=engine_cand.candidate_id,
                            decision="apply_all",
                        )
                    )

        # Gather rules: enabled rules (global + transcript) for condition/is_person_name
        # and rules created by "Accept & Learn" in this session
        rules_by_id: Dict[str, CorrectionRule] = {}
        for rule_dict in self.repo.find_enabled_rules("global"):
            r = _db_rule_to_engine_rule(rule_dict)
            if r.id:
                rules_by_id[r.id] = r
        for rule_dict in self.repo.find_enabled_rules(
            "transcript", transcript_path=transcript_path
        ):
            r = _db_rule_to_engine_rule(rule_dict)
            if r.id:
                rules_by_id[r.id] = r
        for dec in accept_decisions:
            if dec.get("created_rule_id"):
                rule_dict = self.repo.get_rule(dec["created_rule_id"])
                if rule_dict:
                    r = _db_rule_to_engine_rule(rule_dict)
                    if r.id:
                        rules_by_id[r.id] = r

        preview_segments = copy.deepcopy(segments)
        updated_segments, patch_log = apply_corrections(
            segments=preview_segments,
            candidates=engine_candidates,
            transcript_key=transcript_key,
            decisions=engine_decisions,
            rules_by_id=rules_by_id,
        )

        applied = sum(
            1
            for e in patch_log
            if "resolution_policy" not in e
            and e.get("status") not in ("conflict_skipped", "skipped_no_span")
        )

        return {
            "updated_segments": updated_segments,
            "patch_log": patch_log,
            "stats": {
                "applied_count": applied,
                "total_accepted": len(accept_decisions),
            },
        }

    def apply_and_export(
        self, session_id: str, export_path: Optional[str] = None
    ) -> Dict[str, Any]:
        session = self.repo.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        preview = self.compute_preview(session_id)
        updated_segments = preview["updated_segments"]

        transcript_path = session["transcript_path"]
        source_path = Path(transcript_path)
        session_short = session_id[:8]
        if export_path is None:
            export_path = str(
                source_path.parent
                / f"{source_path.stem}_corrected_{session_short}.json"
            )

        save_json({"segments": updated_segments}, export_path)
        self.repo.update_session_status(session_id, "completed")

        # Register artifact if transcript is DB-tracked (so it appears in artifact index)
        transcript_file_id = session.get("transcript_file_id")
        if transcript_file_id is not None:
            try:
                pipeline_run = PipelineRun(
                    transcript_file_id=transcript_file_id,
                    pipeline_version="corrections_studio",
                    pipeline_config_hash=None,
                    pipeline_input_hash=None,
                    cli_args_json={},
                    status="completed",
                )
                self.db_session.add(pipeline_run)
                self.db_session.flush()
                module_run = ModuleRun(
                    pipeline_run_id=pipeline_run.id,
                    transcript_file_id=transcript_file_id,
                    module_name="corrections_studio",
                    module_version=CORRECTIONS_SCHEMA_VERSION,
                    module_config_hash="",
                    module_input_hash=session.get("source_fingerprint", ""),
                    status="completed",
                )
                self.db_session.add(module_run)
                self.db_session.flush()
                export_path_obj = Path(export_path)
                artifact_repo = ArtifactIndexRepository(self.db_session)
                artifact_repo.create_artifact(
                    module_run_id=module_run.id,
                    transcript_file_id=transcript_file_id,
                    artifact_key=f"corrected_{session_short}",
                    relative_path=export_path_obj.name,
                    artifact_root=str(export_path_obj.parent),
                    artifact_type="transcript",
                    artifact_role="primary",
                    content_hash=None,
                )
            except Exception as e:
                logger.warning("Could not register corrections export artifact: %s", e)

        return {
            "export_path": export_path,
            "applied_count": preview["stats"]["applied_count"],
        }

    def get_candidate_local_diff(
        self, session_id: str, candidate_id: str
    ) -> Dict[str, Any]:
        candidate = self.repo.get_candidate(candidate_id)
        if not candidate:
            return {"diffs": []}

        diffs = []
        for occ in candidate["occurrences_json"] or []:
            snippet = occ.get("snippet", "")
            wrong = candidate["wrong_text"]
            suggested = candidate["suggested_text"]
            before = snippet
            after = (
                snippet.replace(wrong, suggested, 1) if wrong in snippet else snippet
            )
            diffs.append(
                {
                    "segment_id": occ.get("segment_id"),
                    "segment_index": occ.get("segment_index"),
                    "speaker": occ.get("speaker"),
                    "time_start": occ.get("time_start"),
                    "time_end": occ.get("time_end"),
                    "before": before,
                    "after": after,
                    "stable_occurrence_key": occ.get("stable_occurrence_key"),
                }
            )
        return {"diffs": diffs}
