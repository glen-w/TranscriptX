"""Contract tests for sidebar workspace state resolution."""

from __future__ import annotations

from types import SimpleNamespace

from transcriptx.web.sidebar_hydration import (
    hydrate_sidebar_state,
    resolve_selected_run,
    resolve_selected_transcript,
)


def test_first_load_with_transcript_options_returns_none_and_ready() -> None:
    ss: dict = {}
    state = hydrate_sidebar_state(
        ss,
        subject_type="transcript",
        explicit_request=False,
        transcript_options=["a", "b"],
        groups=[],
        resolved_subject=None,
        runs=[],
    )
    assert resolve_selected_transcript(ss, ["a", "b"]) is None
    assert state.status == "ready"


def test_selected_transcript_still_exists() -> None:
    ss = {"subject_id": "a"}
    assert resolve_selected_transcript(ss, ["a", "b"]) == "a"


def test_selected_transcript_missing_returns_none() -> None:
    ss = {"subject_id": "gone"}
    assert resolve_selected_transcript(ss, ["a"]) is None


def test_selected_run_still_exists() -> None:
    ss = {"run_id": "r1"}
    assert resolve_selected_run(ss, ["r1", "r2"]) == "r1"


def test_stale_run_returns_first_available() -> None:
    ss = {"run_id": "old"}
    assert resolve_selected_run(ss, ["r2", "r3"]) == "r2"


def test_no_run_options_returns_none() -> None:
    ss = {"run_id": "r1"}
    assert resolve_selected_run(ss, []) is None


def test_empty_transcript_inventory_status_empty() -> None:
    state = hydrate_sidebar_state(
        {},
        subject_type="transcript",
        explicit_request=False,
        transcript_options=[],
        groups=[],
        resolved_subject=None,
        runs=[],
    )
    assert state.status == "empty"


def test_empty_group_inventory_status_empty() -> None:
    state = hydrate_sidebar_state(
        {},
        subject_type="group",
        explicit_request=False,
        transcript_options=[],
        groups=[],
        resolved_subject=None,
        runs=[],
    )
    assert state.status == "empty"


def test_unresolved_subject_status_no_subject() -> None:
    state = hydrate_sidebar_state(
        {"subject_id": "gone"},
        subject_type="transcript",
        explicit_request=False,
        transcript_options=["a"],
        groups=[],
        resolved_subject=None,
        runs=[],
    )
    assert state.status == "no_subject"


def test_explicit_request_with_empty_options_status_loading() -> None:
    state = hydrate_sidebar_state(
        {},
        subject_type="transcript",
        explicit_request=True,
        transcript_options=[],
        groups=[],
        resolved_subject=None,
        runs=[],
    )
    assert state.status == "loading"


def test_ready_when_subject_and_runs_resolved() -> None:
    subject = SimpleNamespace(subject_id="a")
    runs = [SimpleNamespace(run_id="r1")]
    state = hydrate_sidebar_state(
        {"subject_id": "a", "run_id": "r1"},
        subject_type="transcript",
        explicit_request=False,
        transcript_options=["a"],
        groups=[],
        resolved_subject=subject,
        runs=runs,
    )
    assert state.status == "ready"
    assert state.run_id == "r1"
    assert state.run_options == ["r1"]
