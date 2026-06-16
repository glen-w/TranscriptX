"""Edge cases for legacy session normalize, JSONL parse, and replay invariants."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from transcriptx.services.corrections_studio.normalize import (
    normalize_cutover_session_blob,
    session_document_to_persistence,
)
from transcriptx.services.corrections_studio.reconcile import (
    parse_events_jsonl,
    reconcile_snapshot_from_events,
)
from transcriptx.services.corrections_studio.schema import (
    ApplyScope,
    CandidateGenerationDiagnostics,
    DetectorCountsByKind,
    FuzzySkippedReason,
    GenerationManifest,
    ReviewAction,
    ReviewStatus,
    StudioEventEnvelope,
    StudioSessionDocument,
)


def _cand(cid: str, gen: int) -> dict:
    return {
        "candidate_id": cid,
        "generation_id": gen,
        "kind": "acronym",
        "wrong_text": "w",
        "right_text": "r",
        "confidence": 0.5,
        "occurrences": [],
        "review_status": "pending",
    }


@pytest.mark.unit
def test_parse_events_jsonl_skips_blank_lines() -> None:
    e = StudioEventEnvelope(
        session_id="s",
        event_type="session_started",
        event_sequence=1,
        timestamp="2026-01-01T00:00:00Z",
        payload={
            "transcript_path": "/t.json",
            "recorded_transcript_identity_hash": "h",
        },
    )
    raw = e.model_dump(mode="json")
    lines = ["", "  ", json.dumps(raw), ""]
    assert len(parse_events_jsonl(lines)) == 1


@pytest.mark.unit
def test_reconcile_empty_events_raises() -> None:
    with pytest.raises(ValueError, match="No session_started"):
        reconcile_snapshot_from_events(events=[])


@pytest.mark.unit
def test_reconcile_without_session_started_is_invalid_document() -> None:
    """candidates_generated without session_started builds a partial dict; validate fails."""
    e = StudioEventEnvelope(
        session_id="s",
        event_type="candidates_generated",
        event_sequence=1,
        timestamp="2026-01-01T00:00:00Z",
        payload={"generation_id": 1, "candidates": [_cand("c1", 1)]},
    )
    with pytest.raises(ValidationError):
        reconcile_snapshot_from_events(events=[e])


@pytest.mark.unit
def test_normalize_canonical_round_trip_minimal_document() -> None:
    doc = StudioSessionDocument(
        session_id="sid",
        transcript_path="/a.json",
        recorded_transcript_identity_hash="fp",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    again = normalize_cutover_session_blob(doc.model_dump(mode="json"))
    assert again.session_id == doc.session_id
    assert again.transcript_path == doc.transcript_path
    assert (
        again.recorded_transcript_identity_hash == doc.recorded_transcript_identity_hash
    )


@pytest.mark.unit
def test_normalize_legacy_no_candidates_has_no_current_generation() -> None:
    legacy = {
        "session_id": "s",
        "transcript_path": "/p.json",
        "source_fingerprint": "sf",
    }
    doc = normalize_cutover_session_blob(legacy)
    assert doc.candidates == []
    assert doc.current_generation_id is None
    assert doc.current_generation is None


@pytest.mark.unit
def test_normalize_legacy_decision_reject_maps_review_action() -> None:
    legacy = {
        "session_id": "s",
        "transcript_path": "/p.json",
        "source_fingerprint": "sf",
        "candidates": [
            {
                "candidate_id": "c1",
                "kind": "phrase",
                "wrong_text": "w",
                "right_text": "r",
                "confidence": 0.3,
                "occurrences_json": [],
                "status": "pending",
            }
        ],
        "decisions": [
            {
                "decision": "reject",
                "candidate_id": "c1",
                "recorded_at": "2026-01-02T00:00:00Z",
            }
        ],
    }
    doc = normalize_cutover_session_blob(legacy)
    assert len(doc.review_records) == 1
    assert doc.review_records[0].review_action == ReviewAction.reject
    assert doc.review_records[0].apply_scope == ApplyScope.all


@pytest.mark.unit
def test_normalize_legacy_apply_some_sets_selected_scope_and_keys() -> None:
    legacy = {
        "session_id": "s",
        "transcript_path": "/p.json",
        "source_fingerprint": "sf",
        "candidates": [
            {
                "candidate_id": "c1",
                "kind": "phrase",
                "wrong_text": "w",
                "right_text": "r",
                "confidence": 0.3,
                "occurrences_json": [],
                "status": "pending",
            }
        ],
        "decisions": [
            {
                "decision": "apply_some",
                "candidate_id": "c1",
                "selected_occurrence_ids": ["k1", "k2"],
                "recorded_at": "2026-01-02T00:00:00Z",
            }
        ],
    }
    doc = normalize_cutover_session_blob(legacy)
    assert doc.review_records[0].apply_scope == ApplyScope.selected
    assert doc.review_records[0].selected_occurrence_keys == ["k1", "k2"]


@pytest.mark.unit
def test_session_document_to_persistence_drops_ephemeral_flags() -> None:
    doc = StudioSessionDocument(
        session_id="s",
        transcript_path="/t.json",
        recorded_transcript_identity_hash="h",
        candidates_stale=True,
        generation_inputs_stale=True,
    )
    blob = session_document_to_persistence(doc)
    assert "candidates_stale" not in blob
    assert "generation_inputs_stale" not in blob


@pytest.mark.unit
def test_reconcile_learn_action_marks_candidate_accepted() -> None:
    ts = "2026-01-01T00:00:00Z"
    e1 = StudioEventEnvelope(
        session_id="s",
        event_type="session_started",
        event_sequence=1,
        timestamp=ts,
        payload={
            "transcript_path": "/p.json",
            "recorded_transcript_identity_hash": "fh",
        },
    )
    e2 = StudioEventEnvelope(
        session_id="s",
        event_type="candidates_generated",
        event_sequence=2,
        timestamp=ts,
        payload={"generation_id": 1, "candidates": [_cand("c1", 1)]},
    )
    e3 = StudioEventEnvelope(
        session_id="s",
        event_type="review_recorded",
        event_sequence=3,
        timestamp=ts,
        payload={
            "generation_id": 1,
            "candidate_id": "c1",
            "review_action": "learn",
            "apply_scope": "all",
        },
    )
    doc = reconcile_snapshot_from_events(events=[e1, e2, e3])
    assert doc.candidates[0].review_status == ReviewStatus.accepted


@pytest.mark.unit
def test_reconcile_candidates_payload_carries_generation_diagnostics() -> None:
    ts = "2026-01-01T00:00:00Z"
    man = GenerationManifest(transcript_identity_hash="fh", detector_version="d1")
    zeros = DetectorCountsByKind()
    diag = CandidateGenerationDiagnostics(
        pre_dedupe=zeros,
        total_pre_dedupe=0,
        post_dedupe_counts_by_kind=zeros,
        total_after_dedupe=0,
        fuzzy_enabled=False,
        fuzzy_skipped_reason=FuzzySkippedReason.disabled,
    )
    e1 = StudioEventEnvelope(
        session_id="s",
        event_type="session_started",
        event_sequence=1,
        timestamp=ts,
        payload={
            "transcript_path": "/p.json",
            "recorded_transcript_identity_hash": "fh",
        },
    )
    e2 = StudioEventEnvelope(
        session_id="s",
        event_type="candidates_generated",
        event_sequence=2,
        timestamp=ts,
        payload={
            "generation_id": 1,
            "generation_manifest": man.model_dump(mode="json"),
            "generation_manifest_hash": "mh",
            "candidate_ids": ["c1"],
            "candidates": [_cand("c1", 1)],
            "diagnostics": diag.model_dump(mode="json"),
        },
    )
    doc = reconcile_snapshot_from_events(events=[e1, e2])
    assert doc.current_generation is not None
    assert doc.current_generation.generation_diagnostics is not None
    assert doc.current_generation.generation_diagnostics.total_after_dedupe == 0
