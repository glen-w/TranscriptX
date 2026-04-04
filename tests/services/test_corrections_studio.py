"""Corrections Studio schema, compile, normalize, reconcile."""

from __future__ import annotations

import json
from datetime import datetime, timezone


from transcriptx.services.corrections_studio.compile import (
    compile_studio_to_engine_apply,
)
from transcriptx.services.corrections_studio.normalize import (
    normalize_cutover_session_blob,
)
from transcriptx.services.corrections_studio.reconcile import (
    parse_events_jsonl,
    reconcile_snapshot_from_events,
)
from transcriptx.services.corrections_studio.schema import (
    ApplyScope,
    ReviewAction,
    ReviewStatus,
    SessionStartedPayload,
    StudioCandidate,
    StudioEventEnvelope,
    StudioReviewRecord,
    StudioSessionDocument,
)


def test_compile_maps_accept_to_engine_candidates() -> None:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    doc = StudioSessionDocument(
        session_id="s1",
        transcript_path="/tmp/t.json",
        recorded_transcript_identity_hash="abc",
        current_generation_id=1,
        candidates=[
            StudioCandidate(
                candidate_id="c1",
                generation_id=1,
                kind="acronym",
                wrong_text="foo",
                right_text="bar",
                confidence=0.9,
                occurrences=[],
                review_status=ReviewStatus.accepted,
            )
        ],
        review_records=[
            StudioReviewRecord(
                session_id="s1",
                generation_id=1,
                candidate_id="c1",
                review_action=ReviewAction.accept,
                apply_scope=ApplyScope.all,
                recorded_at=now,
                event_sequence=1,
            )
        ],
    )
    out = compile_studio_to_engine_apply(session=doc, segments=[], transcript_key="k")
    assert len(out.engine_candidates) == 1
    assert out.engine_candidates[0].proposed_wrong == "foo"
    assert out.engine_decisions[0].decision == "apply_all"


def test_normalize_legacy_candidate_hash() -> None:
    legacy = {
        "version": 1,
        "session_id": "x",
        "transcript_path": "/a.json",
        "source_fingerprint": "fp",
        "candidates": [
            {
                "candidate_hash": "h1",
                "kind": "acronym",
                "wrong_text": "w",
                "suggested_text": "s",
                "confidence": 0.5,
                "occurrences_json": [],
                "status": "pending",
            }
        ],
        "decisions": [],
    }
    doc = normalize_cutover_session_blob(legacy)
    assert doc.candidates[0].candidate_id == "h1"
    assert doc.candidates[0].right_text == "s"


def test_reconcile_from_events_roundtrip() -> None:
    p = SessionStartedPayload(
        transcript_path="/z.json", recorded_transcript_identity_hash="fh"
    )
    e1 = StudioEventEnvelope(
        session_id="sid",
        event_type="session_started",
        event_sequence=1,
        payload=p.model_dump(mode="json"),
    )
    lines = [json.dumps(e1.model_dump(mode="json"))]
    events = parse_events_jsonl(lines)
    doc = reconcile_snapshot_from_events(events=events)
    assert doc.session_id == "sid"
    assert doc.recorded_transcript_identity_hash == "fh"


def test_compile_ignores_wrong_generation_reviews() -> None:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    doc = StudioSessionDocument(
        session_id="s1",
        transcript_path="/tmp/t.json",
        recorded_transcript_identity_hash="abc",
        current_generation_id=2,
        candidates=[
            StudioCandidate(
                candidate_id="c1",
                generation_id=2,
                kind="acronym",
                wrong_text="a",
                right_text="b",
                confidence=0.9,
                occurrences=[],
                review_status=ReviewStatus.accepted,
            )
        ],
        review_records=[
            StudioReviewRecord(
                session_id="s1",
                generation_id=1,
                candidate_id="c1",
                review_action=ReviewAction.accept,
                apply_scope=ApplyScope.all,
                recorded_at=now,
                event_sequence=1,
            )
        ],
    )
    out = compile_studio_to_engine_apply(session=doc, segments=[], transcript_key="k")
    assert out.engine_candidates == []
