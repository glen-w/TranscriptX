"""Tests for Corrections Studio UI dict helpers."""

from __future__ import annotations

from transcriptx.services.corrections_studio.ui_helpers import (
    studio_candidate_effective_right_text,
    studio_candidate_id,
    studio_candidate_review_status,
    studio_candidate_right_text,
    studio_session_id,
)


def test_studio_session_id_prefers_session_id() -> None:
    assert studio_session_id({"session_id": "a", "id": "b"}) == "a"


def test_studio_session_id_falls_back_to_id() -> None:
    assert studio_session_id({"id": "b"}) == "b"


def test_studio_candidate_id_prefers_candidate_id() -> None:
    assert studio_candidate_id({"candidate_id": "x", "candidate_hash": "y"}) == "x"


def test_studio_candidate_id_falls_back_to_hash() -> None:
    assert studio_candidate_id({"candidate_hash": "y"}) == "y"


def test_studio_candidate_review_status() -> None:
    assert studio_candidate_review_status({"review_status": "accepted"}) == "accepted"
    assert studio_candidate_review_status({"status": "skipped"}) == "skipped"
    assert studio_candidate_review_status({}) == "pending"


def test_studio_candidate_right_text() -> None:
    assert studio_candidate_right_text({"right_text": "ok"}) == "ok"
    assert studio_candidate_right_text({"suggested_text": "legacy"}) == "legacy"
    assert studio_candidate_right_text({}) == ""


def test_studio_candidate_effective_right_text() -> None:
    cand = {
        "candidate_id": "c1",
        "generation_id": 1,
        "kind": "acronym",
        "wrong_text": "a",
        "right_text": "Geo",
        "confidence": 0.9,
        "occurrences": [],
        "review_status": "accepted",
    }
    reviews = [
        {
            "session_id": "s",
            "generation_id": 1,
            "candidate_id": "c1",
            "review_action": "accept",
            "apply_scope": "all",
            "selected_occurrence_keys": [],
            "review_target_text": "GO",
            "recorded_at": "2026-01-01T00:00:00Z",
            "event_sequence": 1,
        }
    ]
    assert studio_candidate_effective_right_text(cand, reviews, 1) == "GO"


def test_studio_session_id_empty_mapping() -> None:
    assert studio_session_id({}) is None


def test_studio_candidate_id_empty_mapping() -> None:
    assert studio_candidate_id({}) is None
