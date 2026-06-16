"""
Temporary cutover: legacy on-disk session dict → StudioSessionDocument.

Delete once no legacy blobs remain in the wild.

**Import surface:** External code should only rely on
``normalize_cutover_session_blob`` for loading legacy session blobs into
``StudioSessionDocument``. Other helpers in this module are internal to the
Corrections Studio package.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from transcriptx.services.corrections_studio.schema import (
    ApplyScope,
    GenerationManifest,
    ReviewAction,
    ReviewStatus,
    StudioCandidate,
    StudioGenerationRecord,
    StudioOccurrence,
    StudioReviewRecord,
    StudioRule,
    StudioSessionDocument,
)
from transcriptx.services.corrections_studio.identity import (
    compute_generation_manifest_hash,
)
from transcriptx.services.corrections_studio.occurrence_keys import (
    stable_occurrence_key,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _review_status_from_str(s: str) -> ReviewStatus:
    try:
        return ReviewStatus(s)
    except ValueError:
        return ReviewStatus.pending


def _occ_from_legacy(o: Dict[str, Any], idx: int, wrong_text: str) -> StudioOccurrence:
    span = o.get("span")
    span_t = None
    if span is not None and len(span) >= 2:
        span_t = (int(span[0]), int(span[1]))
    sk = o.get("stable_occurrence_key")
    if not sk:
        span_start, span_end = (span_t[0], span_t[1]) if span_t else (-1, -1)
        base = stable_occurrence_key(
            str(o.get("segment_id", "")), span_start, span_end, wrong_text
        )
        sk = f"{base}_{idx}" if span_t is None else base
    return StudioOccurrence(
        segment_id=str(o.get("segment_id", "")),
        stable_occurrence_key=str(sk),
        span=span_t,
        snippet=str(o.get("snippet", "")),
        speaker=o.get("speaker"),
        time_start=o.get("time_start"),
        time_end=o.get("time_end"),
        segment_index=int(o.get("segment_index", -1)),
    )


def _rule_from_legacy(k: str, v: Dict[str, Any]) -> StudioRule:
    rid = str(v.get("id") or v.get("rule_hash") or k)
    wrong = v.get("wrong") or v.get("wrong_variants_json") or []
    return StudioRule(
        rule_id=rid,
        rule_type=str(v.get("type") or v.get("rule_type") or "phrase"),
        wrong_variants=list(wrong) if isinstance(wrong, list) else [str(wrong)],
        replacement_text=str(v.get("right") or v.get("replacement_text") or ""),
        scope=str(v.get("scope", "global")),
        confidence=float(v.get("confidence", 0.0)),
        auto_apply=bool(v.get("auto_apply", False)),
        conditions_json=v.get("conditions_json") if v.get("conditions_json") else None,
        is_person_name=bool(v.get("is_person_name", False)),
    )


def normalize_cutover_session_blob(raw: Dict[str, Any]) -> StudioSessionDocument:
    """Upgrade legacy flat session.json to StudioSessionDocument."""
    if raw.get("studio_schema_version"):
        try:
            return StudioSessionDocument.model_validate(raw)
        except Exception:
            pass

    session_id = str(raw.get("session_id", ""))
    transcript_path = str(raw.get("transcript_path", ""))
    fp = str(
        raw.get("recorded_transcript_identity_hash")
        or raw.get("source_fingerprint", "")
    )
    det_ver = str(raw.get("detector_version", "1"))

    gen_id = 1
    if raw.get("current_generation_id") is not None:
        gen_id = int(raw["current_generation_id"])
    elif not (raw.get("candidates") or []):
        gen_id = 0

    current_generation_id: Optional[int] = None
    if raw.get("candidates"):
        current_generation_id = gen_id if gen_id >= 1 else 1

    manifest = GenerationManifest(
        transcript_identity_hash=fp,
        detector_version=det_ver,
        corrections_config_fingerprint="",
        memory_rule_fingerprint="",
        speaker_map_fingerprint="",
        studio_session_rules_fingerprint="",
    )
    mh = compute_generation_manifest_hash(manifest)

    candidates: List[StudioCandidate] = []
    for row in raw.get("candidates") or []:
        cid = str(row.get("candidate_id") or row.get("candidate_hash") or "")
        if not cid:
            continue
        occs = row.get("occurrences_json") or []
        wrong = str(row.get("wrong_text", ""))
        right = str(row.get("right_text") or row.get("suggested_text", ""))
        candidates.append(
            StudioCandidate(
                candidate_id=cid,
                generation_id=current_generation_id or 1,
                kind=str(row.get("kind", "phrase")),
                wrong_text=wrong,
                right_text=right,
                confidence=float(row.get("confidence", 0.0)),
                rule_id=row.get("rule_id"),
                occurrences=[
                    _occ_from_legacy(o, i, wrong)
                    for i, o in enumerate(occs)
                    if isinstance(o, dict)
                ],
                review_status=_review_status_from_str(
                    str(row.get("status", "pending"))
                ),
            )
        )

    review_records: List[StudioReviewRecord] = []
    seq = 0
    for d in raw.get("review_records") or []:
        seq += 1
        # already canonical
        try:
            review_records.append(StudioReviewRecord.model_validate(d))
        except Exception:
            continue

    if not review_records:
        for d in raw.get("decisions") or []:
            seq += 1
            dec = str(d.get("decision", "skip"))
            if dec == "learn":
                ra = ReviewAction.learn
            elif dec in ("apply_all", "apply_some"):
                ra = ReviewAction.accept
            else:
                try:
                    ra = ReviewAction(dec)
                except ValueError:
                    ra = ReviewAction.skip
            nr = d.get("new_rule") if isinstance(d.get("new_rule"), dict) else None
            learn_id = str(nr["id"]) if nr and nr.get("id") else None
            sels = d.get("selected_occurrence_ids") or []
            review_records.append(
                StudioReviewRecord(
                    session_id=session_id,
                    generation_id=current_generation_id or 1,
                    candidate_id=str(d.get("candidate_id", "")),
                    review_action=ra,
                    apply_scope=ApplyScope.selected if sels else ApplyScope.all,
                    selected_occurrence_keys=[str(x) for x in sels],
                    learn_intent=None,
                    learn_rule_id=learn_id,
                    recorded_at=str(d.get("recorded_at") or _now_iso()),
                    event_sequence=seq,
                )
            )

    rules: Dict[str, StudioRule] = {}
    for k, v in (raw.get("rules") or {}).items():
        if isinstance(v, dict):
            sr = _rule_from_legacy(str(k), v)
            rules[sr.rule_id] = sr

    gen_record = None
    if current_generation_id is not None:
        gen_record = StudioGenerationRecord(
            generation_id=current_generation_id,
            generation_manifest=manifest,
            generation_manifest_hash=mh,
            candidate_ids=[c.candidate_id for c in candidates],
            completed_at=str(
                raw.get("updated_at") or raw.get("created_at") or _now_iso()
            ),
        )

    return StudioSessionDocument(
        studio_schema_version=1,
        session_id=session_id,
        transcript_path=transcript_path,
        recorded_transcript_identity_hash=fp,
        current_generation_id=current_generation_id,
        current_generation=gen_record,
        candidates=candidates,
        review_records=review_records,
        rules=rules,
        created_at=str(raw.get("created_at") or _now_iso()),
        updated_at=str(raw.get("updated_at") or _now_iso()),
        status=str(raw.get("status", "active")),
        candidates_stale=bool(raw.get("candidates_stale", False)),
    )


def session_document_to_persistence(doc: StudioSessionDocument) -> Dict[str, Any]:
    """JSON-serializable dict for session.json (drops ephemeral UI fields)."""
    d = doc.model_dump(
        mode="json", exclude={"candidates_stale", "generation_inputs_stale"}
    )
    return d
