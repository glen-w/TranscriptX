"""Tests for navigation contracts."""

from __future__ import annotations

from pathlib import Path

from transcriptx.app.models.metadata import TranscriptMetadata
from transcriptx.web.navigation import (
    apply_library_rename_navigation,
    build_prerequisites,
    consume_library_transcript_nav,
    evaluate_page_access,
    get_page_spec,
    library_transcript_index,
    page_requires_workspace_hydration,
)
from transcriptx.web.services.subject_service import SubjectService
from transcriptx.web.sidebar_state import (
    SidebarSelectionResult,
    apply_sidebar_selection,
)
from transcriptx.web.state import LIBRARY_NAV_TRANSCRIPT_PATH


def test_library_rename_navigation_sets_canonical_context_and_one_shot_nav(
    monkeypatch, tmp_path
) -> None:
    from transcriptx.web import navigation as nav_mod

    transcript = tmp_path / "interview.json"
    transcript.write_text("{}", encoding="utf-8")
    other = tmp_path / "other.json"
    other.write_text("{}", encoding="utf-8")
    transcripts = [
        TranscriptMetadata(path=other, base_name="other"),
        TranscriptMetadata(path=transcript, base_name="interview"),
    ]

    ss: dict[str, object] = {}
    monkeypatch.setattr(
        nav_mod,
        "make_session_path_resolver",
        lambda: (lambda _p: ("slug-1", "run-1")),
    )

    apply_library_rename_navigation(ss, transcript)

    assert ss["subject_type"] == "transcript"
    assert ss["subject_id"] == "slug-1"
    assert ss["run_id"] == "run-1"
    assert ss[LIBRARY_NAV_TRANSCRIPT_PATH] == str(transcript.resolve())
    assert "selected_transcript_path" not in ss

    consume_library_transcript_nav(ss, transcripts)
    assert LIBRARY_NAV_TRANSCRIPT_PATH not in ss
    assert ss["library_transcript_select"] == 2


def test_library_nav_path_is_one_shot_and_does_not_write_legacy_path(
    monkeypatch, tmp_path
) -> None:
    from transcriptx.web import navigation as nav_mod

    transcript = tmp_path / "call.json"
    transcript.write_text("{}", encoding="utf-8")
    ss: dict[str, object] = {
        LIBRARY_NAV_TRANSCRIPT_PATH: str(transcript.resolve()),
    }
    monkeypatch.setattr(
        nav_mod,
        "make_session_path_resolver",
        lambda: (lambda _p: None),
    )

    SubjectService.set_transcript_context_from_path(ss, transcript)
    consume_library_transcript_nav(
        ss,
        [TranscriptMetadata(path=transcript, base_name="call")],
    )

    assert LIBRARY_NAV_TRANSCRIPT_PATH not in ss
    assert ss["subject_type"] == "transcript"
    assert "selected_transcript_path" not in ss


def test_library_transcript_index_matches_resolved_paths(tmp_path) -> None:
    transcript = tmp_path / "nested" / "call.json"
    transcript.parent.mkdir()
    transcript.write_text("{}", encoding="utf-8")
    meta = TranscriptMetadata(path=transcript, base_name="call")
    assert library_transcript_index([meta], str(transcript)) == 1
    assert library_transcript_index([meta], Path("missing.json")) == 0


def test_set_transcript_context_from_path_updates_subject_tuple(monkeypatch) -> None:
    ss: dict[str, str] = {}
    monkeypatch.setattr(
        "transcriptx.web.services.transcript_context_resolver.load_index",
        lambda: {"transcripts": {}},
    )

    SubjectService.set_transcript_context_from_path(
        ss,
        "/tmp/test.json",
        session_resolver=lambda _p: ("slug-2", "run-2"),
    )

    assert "selected_transcript_path" not in ss
    assert ss["subject_type"] == "transcript"
    assert ss["subject_id"] == "slug-2"
    assert ss["run_id"] == "run-2"


def test_page_prerequisite_access_uses_readiness_flags() -> None:
    prereqs = build_prerequisites()
    denied = evaluate_page_access(
        "Overview",
        prereqs,
        {"subject_ready": True, "run_scoped_ready": False, "transcript_ready": False},
    )
    assert denied.allowed is False
    allowed = evaluate_page_access(
        "Overview",
        prereqs,
        {"subject_ready": True, "run_scoped_ready": True, "transcript_ready": True},
    )
    assert allowed.allowed is True


def test_sidebar_selection_result_updates_context() -> None:
    ss: dict[str, str] = {}
    apply_sidebar_selection(
        ss,
        SidebarSelectionResult(
            subject_type="group",
            subject_id="group-1",
            run_id="run-7",
        ),
    )
    assert ss["subject_type"] == "group"
    assert ss["subject_id"] == "group-1"
    assert ss["run_id"] == "run-7"


def test_page_hydration_gate_follows_required_context_only() -> None:
    assert page_requires_workspace_hydration("Home") is False
    assert page_requires_workspace_hydration("Library") is False
    assert page_requires_workspace_hydration("Search") is False
    assert page_requires_workspace_hydration("Settings") is False
    assert page_requires_workspace_hydration("Charts") is True
    assert page_requires_workspace_hydration("Overview") is True
    assert page_requires_workspace_hydration("Transcript") is True


def test_make_session_path_resolver_is_lazy(monkeypatch) -> None:
    """Indexed slug hits must not pay for rich session listing."""
    from transcriptx.web import navigation as nav

    calls: list[int] = []

    def _boom():
        calls.append(1)
        raise AssertionError("sessions must not load until resolver is called")

    monkeypatch.setattr(
        "transcriptx.web.cache_helpers.cached_list_available_sessions",
        _boom,
    )
    resolver = nav.make_session_path_resolver()
    assert calls == []
    # Invoking the resolver triggers the listing once.
    monkeypatch.setattr(
        "transcriptx.web.cache_helpers.cached_list_available_sessions",
        lambda: calls.append(1) or [],
    )
    monkeypatch.setattr(
        "transcriptx.web.services.file_service.FileService.resolve_session_for_transcript_path",
        lambda _path, _sessions: None,
    )
    assert resolver("/tmp/x.json") is None
    assert calls == [1]


def test_unknown_page_spec_is_non_hydrating() -> None:
    spec = get_page_spec("Totally Unknown Page")
    assert spec.required_context == "none"
    assert page_requires_workspace_hydration("Totally Unknown Page") is False


def test_should_show_context_bar_hides_home_ingest_tools_settings() -> None:
    from transcriptx.web.navigation import PAGE_SPECS, should_show_context_bar

    assert should_show_context_bar("Home") is False
    assert should_show_context_bar("Transcribe Audio") is False
    assert should_show_context_bar("Import Transcript") is False
    assert should_show_context_bar(None) is False

    for spec in PAGE_SPECS:
        shown = should_show_context_bar(spec.key)
        if spec.key in {"Home", "Transcribe Audio", "Import Transcript"}:
            assert shown is False
        elif spec.section in {"tools", "settings"}:
            assert shown is False
        else:
            assert shown is True


def test_build_prerequisites_matches_page_specs() -> None:
    from transcriptx.web.navigation import PAGE_SPECS

    prereqs = build_prerequisites()
    for spec in PAGE_SPECS:
        prereq = prereqs[spec.key]
        assert prereq.required_context == spec.required_context
        assert prereq.allowed_fallback == spec.allowed_fallback
        assert prereq.may_mutate_context == spec.may_mutate_context


def test_navigate_to_transcript_from_path_binds_run_when_index_has_empty_runs(
    monkeypatch, tmp_path
) -> None:
    """Appearances Open transcript must not bounce to Home when index lacks runs."""
    import streamlit as st

    from transcriptx.web import navigation as nav_mod
    from transcriptx.web.state import PAGE_KEY

    transcript = tmp_path / "interview.json"
    transcript.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.web.services.transcript_context_resolver.load_index",
        lambda: {
            "transcripts": {
                "key-1": {
                    "slug": "interview",
                    "source_path": str(transcript),
                    "runs": [],
                }
            }
        },
    )
    monkeypatch.setattr(
        nav_mod,
        "make_session_path_resolver",
        lambda: (lambda _p: ("interview", "run-42")),
    )
    rerun = {"count": 0}
    monkeypatch.setattr(
        st, "rerun", lambda: rerun.__setitem__("count", rerun["count"] + 1)
    )
    st.session_state.clear()

    assert nav_mod.navigate_to_transcript_from_path(transcript) is True
    assert st.session_state[PAGE_KEY] == "Transcript"
    assert st.session_state["subject_id"] == "interview"
    assert st.session_state["run_id"] == "run-42"
    assert rerun["count"] == 1


def test_navigate_to_transcript_from_path_returns_false_without_run(
    monkeypatch, tmp_path
) -> None:
    import streamlit as st

    from transcriptx.web import navigation as nav_mod

    transcript = tmp_path / "orphan.json"
    transcript.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.web.services.transcript_context_resolver.load_index",
        lambda: {"transcripts": {}},
    )
    monkeypatch.setattr(
        nav_mod,
        "make_session_path_resolver",
        lambda: (lambda _p: None),
    )
    st.session_state.clear()

    assert nav_mod.navigate_to_transcript_from_path(transcript) is False
    assert (
        "page" not in st.session_state or st.session_state.get("page") != "Transcript"
    )
