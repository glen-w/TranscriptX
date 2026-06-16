"""Corrections Studio schema, compile, normalize, reconcile.

Fuzzy wiring, diagnostics, staleness, filters, and UI copy helpers are covered in
``test_corrections_studio_fuzzy_manifest.py`` (kept separate: path names containing
``generation`` are tagged ``requires_models`` by conftest).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from transcriptx.core.corrections.apply import apply_corrections
from transcriptx.core.corrections.detect import resolve_segment_id
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
    StudioOccurrence,
    StudioReviewRecord,
    StudioRule,
    StudioSessionDocument,
)
from transcriptx.services.corrections_studio.service import CorrectionService


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
    assert out.engine_candidates[0].proposed_right == "bar"
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


def test_compile_empty_when_no_current_generation() -> None:
    doc = StudioSessionDocument(
        session_id="s1",
        transcript_path="/tmp/t.json",
        recorded_transcript_identity_hash="abc",
        current_generation_id=None,
        candidates=[],
    )
    out = compile_studio_to_engine_apply(session=doc, segments=[], transcript_key="k")
    assert out.engine_candidates == []
    assert out.engine_decisions == []
    assert out.rules_by_id == {}


def test_compile_reject_omits_candidate() -> None:
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
                review_status=ReviewStatus.rejected,
            )
        ],
        review_records=[
            StudioReviewRecord(
                session_id="s1",
                generation_id=1,
                candidate_id="c1",
                review_action=ReviewAction.reject,
                apply_scope=ApplyScope.all,
                recorded_at=now,
                event_sequence=1,
            )
        ],
    )
    out = compile_studio_to_engine_apply(session=doc, segments=[], transcript_key="k")
    assert out.engine_candidates == []
    assert out.engine_decisions == []


def test_compile_apply_some_sets_decision_and_occurrence_ids() -> None:
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
                kind="consistency",
                wrong_text="foo",
                right_text="bar",
                confidence=0.8,
                occurrences=[
                    StudioOccurrence(
                        segment_id="seg0",
                        stable_occurrence_key="occ-a",
                        snippet="foo",
                    )
                ],
                review_status=ReviewStatus.accepted,
            )
        ],
        review_records=[
            StudioReviewRecord(
                session_id="s1",
                generation_id=1,
                candidate_id="c1",
                review_action=ReviewAction.accept,
                apply_scope=ApplyScope.selected,
                selected_occurrence_keys=["occ-a"],
                recorded_at=now,
                event_sequence=1,
            )
        ],
    )
    out = compile_studio_to_engine_apply(session=doc, segments=[], transcript_key="k")
    assert len(out.engine_decisions) == 1
    assert out.engine_decisions[0].decision == "apply_some"
    assert out.engine_decisions[0].selected_occurrence_ids == ["occ-a"]


def test_compile_review_target_overrides_proposed_right() -> None:
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
                kind="consistency",
                wrong_text="GEO",
                right_text="Geo",
                confidence=1.0,
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
                review_target_text="GO",
                recorded_at=now,
                event_sequence=1,
            )
        ],
    )
    out = compile_studio_to_engine_apply(session=doc, segments=[], transcript_key="k")
    assert len(out.engine_candidates) == 1
    assert out.engine_candidates[0].proposed_right == "GO"


def test_compile_latest_review_wins_custom_target() -> None:
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
                review_target_text="first",
                recorded_at=now,
                event_sequence=1,
            ),
            StudioReviewRecord(
                session_id="s1",
                generation_id=1,
                candidate_id="c1",
                review_action=ReviewAction.accept,
                apply_scope=ApplyScope.all,
                review_target_text="second",
                recorded_at=now,
                event_sequence=2,
            ),
        ],
    )
    out = compile_studio_to_engine_apply(session=doc, segments=[], transcript_key="k")
    assert out.engine_candidates[0].proposed_right == "second"


def test_compile_mixed_candidates_respects_per_candidate_review_target() -> None:
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
                wrong_text="a",
                right_text="A1",
                confidence=0.9,
                occurrences=[],
                review_status=ReviewStatus.accepted,
            ),
            StudioCandidate(
                candidate_id="c2",
                generation_id=1,
                kind="acronym",
                wrong_text="b",
                right_text="B1",
                confidence=0.9,
                occurrences=[],
                review_status=ReviewStatus.accepted,
            ),
            StudioCandidate(
                candidate_id="c3",
                generation_id=1,
                kind="acronym",
                wrong_text="c",
                right_text="C1",
                confidence=0.9,
                occurrences=[],
                review_status=ReviewStatus.accepted,
            ),
        ],
        review_records=[
            StudioReviewRecord(
                session_id="s1",
                generation_id=1,
                candidate_id="c1",
                review_action=ReviewAction.accept,
                apply_scope=ApplyScope.all,
                review_target_text=None,
                recorded_at=now,
                event_sequence=1,
            ),
            StudioReviewRecord(
                session_id="s1",
                generation_id=1,
                candidate_id="c2",
                review_action=ReviewAction.accept,
                apply_scope=ApplyScope.all,
                review_target_text="B2",
                recorded_at=now,
                event_sequence=2,
            ),
            StudioReviewRecord(
                session_id="s1",
                generation_id=1,
                candidate_id="c3",
                review_action=ReviewAction.accept,
                apply_scope=ApplyScope.all,
                review_target_text=None,
                recorded_at=now,
                event_sequence=3,
            ),
        ],
    )
    out = compile_studio_to_engine_apply(session=doc, segments=[], transcript_key="k")
    by_id = {c.candidate_id: c.proposed_right for c in out.engine_candidates}
    assert by_id["c1"] == "A1"
    assert by_id["c2"] == "B2"
    assert by_id["c3"] == "C1"


def test_compile_whitespace_only_review_target_falls_back_to_candidate_right() -> None:
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
                wrong_text="a",
                right_text="Fallback",
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
                review_target_text="   ",
                recorded_at=now,
                event_sequence=1,
            )
        ],
    )
    out = compile_studio_to_engine_apply(session=doc, segments=[], transcript_key="k")
    assert out.engine_candidates[0].proposed_right == "Fallback"
    assert out.engine_candidates[0].proposed_right != ""


def test_compile_learn_attaches_new_rule() -> None:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    rule = StudioRule(
        rule_id="rule-1",
        rule_type="phrase",
        wrong_variants=["typo"],
        replacement_text="fixed",
    )
    doc = StudioSessionDocument(
        session_id="s1",
        transcript_path="/tmp/t.json",
        recorded_transcript_identity_hash="abc",
        current_generation_id=1,
        candidates=[
            StudioCandidate(
                candidate_id="c1",
                generation_id=1,
                kind="consistency",
                wrong_text="typo",
                right_text="fixed",
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
                review_action=ReviewAction.learn,
                apply_scope=ApplyScope.all,
                learn_rule_id="rule-1",
                recorded_at=now,
                event_sequence=1,
            )
        ],
        rules={"rule-1": rule},
    )
    out = compile_studio_to_engine_apply(session=doc, segments=[], transcript_key="k")
    assert len(out.engine_decisions) == 1
    assert out.engine_decisions[0].new_rule is not None
    assert out.engine_decisions[0].new_rule.id == "rule-1"
    assert "rule-1" in out.rules_by_id


def test_reconcile_raises_without_session_started() -> None:
    with pytest.raises(ValueError, match="session_started"):
        reconcile_snapshot_from_events(events=[])


def test_reconcile_review_target_text_roundtrip() -> None:
    ts = "2026-01-15T12:00:00Z"
    e1 = StudioEventEnvelope(
        session_id="sid",
        event_type="session_started",
        event_sequence=1,
        timestamp=ts,
        payload={
            "transcript_path": "/t.json",
            "recorded_transcript_identity_hash": "fh",
        },
    )
    e2 = StudioEventEnvelope(
        session_id="sid",
        event_type="candidates_generated",
        event_sequence=2,
        timestamp=ts,
        payload={
            "generation_id": 1,
            "candidates": [
                {
                    "candidate_id": "c1",
                    "generation_id": 1,
                    "kind": "acronym",
                    "wrong_text": "x",
                    "right_text": "y",
                    "confidence": 0.5,
                    "occurrences": [],
                    "review_status": "pending",
                }
            ],
        },
    )
    e3 = StudioEventEnvelope(
        session_id="sid",
        event_type="review_recorded",
        event_sequence=3,
        timestamp=ts,
        payload={
            "generation_id": 1,
            "candidate_id": "c1",
            "review_action": "accept",
            "apply_scope": "all",
            "review_target_text": "  Z  ",
        },
    )
    doc = reconcile_snapshot_from_events(events=[e1, e2, e3])
    assert doc.review_records[0].review_target_text == "Z"


def test_reconcile_review_updates_candidate_status() -> None:
    ts = "2026-01-15T12:00:00Z"
    e1 = StudioEventEnvelope(
        session_id="sid",
        event_type="session_started",
        event_sequence=1,
        timestamp=ts,
        payload={
            "transcript_path": "/t.json",
            "recorded_transcript_identity_hash": "fh",
        },
    )
    e2 = StudioEventEnvelope(
        session_id="sid",
        event_type="candidates_generated",
        event_sequence=2,
        timestamp=ts,
        payload={
            "generation_id": 1,
            "candidates": [
                {
                    "candidate_id": "c1",
                    "generation_id": 1,
                    "kind": "acronym",
                    "wrong_text": "x",
                    "right_text": "y",
                    "confidence": 0.5,
                    "occurrences": [],
                    "review_status": "pending",
                }
            ],
        },
    )
    e3 = StudioEventEnvelope(
        session_id="sid",
        event_type="review_recorded",
        event_sequence=3,
        timestamp=ts,
        payload={
            "generation_id": 1,
            "candidate_id": "c1",
            "review_action": "reject",
            "apply_scope": "all",
        },
    )
    events = [e1, e2, e3]
    doc = reconcile_snapshot_from_events(events=events)
    assert doc.current_generation_id == 1
    assert len(doc.candidates) == 1
    assert doc.candidates[0].review_status == ReviewStatus.rejected
    assert len(doc.review_records) == 1
    assert doc.review_records[0].review_action == ReviewAction.reject


def test_reconcile_updated_at_follows_highest_event_sequence_not_input_order() -> None:
    """Unsorted input must still yield updated_at from the last envelope in sorted replay order."""
    ts_early = "2026-01-01T00:00:00Z"
    ts_mid = "2026-01-02T00:00:00Z"
    ts_last = "2026-01-03T00:00:00Z"
    e1 = StudioEventEnvelope(
        session_id="sid",
        event_type="session_started",
        event_sequence=1,
        timestamp=ts_early,
        payload={
            "transcript_path": "/t.json",
            "recorded_transcript_identity_hash": "fh",
        },
    )
    e2 = StudioEventEnvelope(
        session_id="sid",
        event_type="candidates_generated",
        event_sequence=2,
        timestamp=ts_mid,
        payload={
            "generation_id": 1,
            "candidates": [
                {
                    "candidate_id": "c1",
                    "generation_id": 1,
                    "kind": "acronym",
                    "wrong_text": "x",
                    "right_text": "y",
                    "confidence": 0.5,
                    "occurrences": [],
                    "review_status": "pending",
                }
            ],
        },
    )
    e3 = StudioEventEnvelope(
        session_id="sid",
        event_type="review_recorded",
        event_sequence=3,
        timestamp=ts_last,
        payload={
            "generation_id": 1,
            "candidate_id": "c1",
            "review_action": "accept",
            "apply_scope": "all",
        },
    )
    doc = reconcile_snapshot_from_events(events=[e3, e1, e2])
    assert doc.updated_at == ts_last


def test_dedupe_studio_rule_dict_via_db_rule_adapter_distinct_conditions() -> None:
    """Same wrong/right text with different conditions_json stays split (studio → engine dict shape)."""
    from transcriptx.core.corrections.models import Candidate as EngineCandidate
    from transcriptx.core.corrections.models import Occurrence
    from transcriptx.core.corrections.workflow import dedupe_candidates
    from transcriptx.services.corrections_studio.candidate_service import (
        _db_rule_to_engine_rule,
    )

    def _studio_rule_engine_dict(sr: StudioRule) -> dict:
        return {
            "id": sr.rule_id,
            "type": sr.rule_type,
            "wrong": sr.wrong_variants,
            "right": sr.replacement_text,
            "scope": sr.scope,
            "confidence": sr.confidence,
            "auto_apply": sr.auto_apply,
            "conditions_json": sr.conditions_json,
            "is_person_name": sr.is_person_name,
        }

    sr_a = StudioRule(
        rule_id="rule-a",
        rule_type="token",
        wrong_variants=["foo"],
        replacement_text="bar",
        scope="global",
        conditions_json={"speaker": "Alice"},
    )
    sr_b = StudioRule(
        rule_id="rule-b",
        rule_type="token",
        wrong_variants=["foo"],
        replacement_text="bar",
        scope="global",
        conditions_json={"speaker": "Bob"},
    )
    ra = _db_rule_to_engine_rule(_studio_rule_engine_dict(sr_a))
    rb = _db_rule_to_engine_rule(_studio_rule_engine_dict(sr_b))
    seg = "s0"
    o1 = Occurrence(segment_id=seg, span=(0, 3), snippet="foo")
    o2 = Occurrence(segment_id=seg, span=(0, 3), snippet="foo")
    c1 = EngineCandidate(
        proposed_wrong="FOO",
        proposed_right="bar",
        kind="memory_hit",
        confidence=0.9,
        rule_id=ra.id,
        occurrences=[o1],
    )
    c2 = EngineCandidate(
        proposed_wrong="foo",
        proposed_right="BAR",
        kind="memory_hit",
        confidence=0.8,
        rule_id=rb.id,
        occurrences=[o2],
    )
    merged = dedupe_candidates([c1, c2], rules_by_id={ra.id: ra, rb.id: rb})
    assert len(merged) == 2


def test_compile_after_reconcile_accept_produces_apply_all() -> None:
    ts = "2026-01-01T00:00:00Z"
    e1 = StudioEventEnvelope(
        session_id="sid",
        event_type="session_started",
        event_sequence=1,
        timestamp=ts,
        payload={
            "transcript_path": "/t.json",
            "recorded_transcript_identity_hash": "fh",
        },
    )
    e2 = StudioEventEnvelope(
        session_id="sid",
        event_type="candidates_generated",
        event_sequence=2,
        timestamp=ts,
        payload={
            "generation_id": 1,
            "candidates": [
                {
                    "candidate_id": "c1",
                    "generation_id": 1,
                    "kind": "acronym",
                    "wrong_text": "x",
                    "right_text": "y",
                    "confidence": 0.5,
                    "occurrences": [],
                    "review_status": "pending",
                }
            ],
        },
    )
    e3 = StudioEventEnvelope(
        session_id="sid",
        event_type="review_recorded",
        event_sequence=3,
        timestamp=ts,
        payload={
            "generation_id": 1,
            "candidate_id": "c1",
            "review_action": "accept",
            "apply_scope": "all",
        },
    )
    doc = reconcile_snapshot_from_events(events=[e1, e2, e3])
    out = compile_studio_to_engine_apply(session=doc, segments=[], transcript_key="k")
    assert len(out.engine_candidates) == 1
    assert out.engine_decisions[0].decision == "apply_all"


def test_compile_plus_apply_uses_review_target() -> None:
    transcript_key = "tk"
    segments = [
        {"text": "see GEO today", "speaker": "S", "start": 0.0, "end": 1.0},
    ]
    seg_id = resolve_segment_id(segments[0], transcript_key, segment_index=0)
    text = segments[0]["text"]
    span = (text.index("GEO"), text.index("GEO") + 3)
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
                kind="consistency",
                wrong_text="GEO",
                right_text="Geo",
                confidence=1.0,
                occurrences=[
                    StudioOccurrence(
                        segment_id=seg_id,
                        stable_occurrence_key="occ1",
                        span=span,
                        snippet=text,
                        segment_index=0,
                    )
                ],
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
                review_target_text="GO",
                recorded_at=now,
                event_sequence=1,
            )
        ],
    )
    compiled = compile_studio_to_engine_apply(
        session=doc, segments=segments, transcript_key=transcript_key
    )
    updated, _ = apply_corrections(
        segments,
        compiled.engine_candidates,
        transcript_key,
        decisions=compiled.engine_decisions,
        rules_by_id=compiled.rules_by_id,
    )
    assert "GO" in updated[0]["text"]
    assert "GEO" not in updated[0]["text"]


def test_service_get_candidate_local_diff_transient_target() -> None:
    svc = CorrectionService()
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
                occurrences=[
                    StudioOccurrence(
                        segment_id="seg",
                        stable_occurrence_key="ok",
                        snippet="x foo y",
                        segment_index=0,
                    )
                ],
                review_status=ReviewStatus.pending,
            )
        ],
        review_records=[],
    )
    svc._session_svc.load_document = MagicMock(return_value=doc)
    r = svc.get_candidate_local_diff("s1", "c1", transient_target_raw="baz")
    assert r.diffs[0].after == "x baz y"
