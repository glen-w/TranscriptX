"""Unit tests for Streamlit page context readiness gates."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.web.navigation import context_readiness, evaluate_page_access

pytestmark = [pytest.mark.unit]


def test_context_readiness_transcript_requires_run_id(monkeypatch) -> None:
    """Transcript VIEW pages need subject + run_id (not subject alone)."""
    subject = SimpleNamespace(subject_type="transcript", subject_id="planning_review")
    monkeypatch.setattr(
        "transcriptx.web.navigation.SubjectService.resolve_current_subject",
        staticmethod(lambda _s: subject),
    )
    without_run = context_readiness({"subject_id": "planning_review"})
    assert without_run["subject_ready"] is True
    assert without_run["transcript_ready"] is False
    assert without_run["run_scoped_ready"] is False

    with_run = context_readiness(
        {"subject_id": "planning_review", "run_id": "20240101_120000"}
    )
    assert with_run["transcript_ready"] is True
    assert with_run["run_scoped_ready"] is True


def test_context_readiness_group_subject_is_transcript_ready(monkeypatch) -> None:
    """Group subjects unlock transcript_or_group pages without a run_id."""
    subject = SimpleNamespace(subject_type="group", subject_id="group-uuid")
    monkeypatch.setattr(
        "transcriptx.web.navigation.SubjectService.resolve_current_subject",
        staticmethod(lambda _s: subject),
    )
    readiness = context_readiness({"subject_id": "group-uuid"})
    assert readiness["subject_ready"] is True
    assert readiness["transcript_ready"] is True
    assert readiness["run_scoped_ready"] is False


def test_evaluate_page_access_transcript_view_gate() -> None:
    """Transcript page is blocked until transcript_ready is true."""
    prereq = {
        "Transcript": SimpleNamespace(required_context="transcript_or_group"),
        "Library": SimpleNamespace(required_context="none"),
    }
    blocked = evaluate_page_access(
        "Transcript",
        prereq,
        {
            "subject_ready": True,
            "run_scoped_ready": False,
            "transcript_ready": False,
        },
    )
    assert blocked.allowed is False

    allowed = evaluate_page_access(
        "Transcript",
        prereq,
        {
            "subject_ready": True,
            "run_scoped_ready": True,
            "transcript_ready": True,
        },
    )
    assert allowed.allowed is True

    library = evaluate_page_access(
        "Library",
        prereq,
        {
            "subject_ready": False,
            "run_scoped_ready": False,
            "transcript_ready": False,
        },
    )
    assert library.allowed is True
