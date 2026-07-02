from __future__ import annotations

from pathlib import Path

from transcriptx.app.models.metadata import TranscriptMetadata
from transcriptx.web.navigation import (
    apply_library_rename_navigation,
    apply_transcript_selection_context,
    build_prerequisites,
    consume_library_transcript_nav,
    evaluate_page_access,
    get_page_spec,
    library_transcript_index,
    normalize_navigation_context_from_session,
    page_requires_workspace_hydration,
    session_only_context_readiness,
)
from transcriptx.web.sidebar_state import (
    SidebarSelectionResult,
    apply_sidebar_selection,
)


def test_library_rename_navigation_preselects_library_selectbox(
    monkeypatch, tmp_path
) -> None:
    from transcriptx.web import navigation as nav_mod
    from transcriptx.web.state import (
        LIBRARY_NAV_TRANSCRIPT_PATH,
        SELECTED_TRANSCRIPT_PATH,
    )

    transcript = tmp_path / "interview.json"
    transcript.write_text("{}", encoding="utf-8")
    other = tmp_path / "other.json"
    other.write_text("{}", encoding="utf-8")
    transcripts = [
        TranscriptMetadata(path=other, base_name="other"),
        TranscriptMetadata(path=transcript, base_name="interview"),
    ]

    ss: dict[str, object] = {}
    monkeypatch.setattr(nav_mod, "cached_list_available_sessions", lambda: [])
    monkeypatch.setattr(
        nav_mod.FileService,
        "resolve_session_for_transcript_path",
        lambda _p, _s: ("slug-1", "run-1"),
    )

    apply_library_rename_navigation(ss, transcript)

    assert ss[SELECTED_TRANSCRIPT_PATH] == str(transcript.resolve())
    assert ss[LIBRARY_NAV_TRANSCRIPT_PATH] == str(transcript.resolve())

    consume_library_transcript_nav(ss, transcripts)
    assert LIBRARY_NAV_TRANSCRIPT_PATH not in ss
    assert ss["library_transcript_select"] == 2


def test_library_transcript_index_matches_resolved_paths(tmp_path) -> None:
    transcript = tmp_path / "nested" / "call.json"
    transcript.parent.mkdir()
    transcript.write_text("{}", encoding="utf-8")
    meta = TranscriptMetadata(path=transcript, base_name="call")
    assert library_transcript_index([meta], str(transcript)) == 1
    assert library_transcript_index([meta], Path("missing.json")) == 0


def test_legacy_transcript_path_normalizes_to_canonical_context(monkeypatch) -> None:
    from transcriptx.web import navigation as nav_mod

    ss = {"selected_transcript_path": "/tmp/a.json"}
    monkeypatch.setattr(nav_mod, "cached_list_available_sessions", lambda: [])
    monkeypatch.setattr(
        nav_mod.FileService,
        "resolve_session_for_transcript_path",
        lambda _p, _s: ("slug-1", "run-9"),
    )
    changed = normalize_navigation_context_from_session(ss)
    assert changed is True
    assert ss["subject_type"] == "transcript"
    assert ss["subject_id"] == "slug-1"
    assert ss["run_id"] == "run-9"


def test_apply_transcript_selection_context_updates_subject_tuple(monkeypatch) -> None:
    from transcriptx.web import navigation as nav_mod

    ss: dict[str, str] = {}
    monkeypatch.setattr(nav_mod, "cached_list_available_sessions", lambda: [])
    monkeypatch.setattr(
        nav_mod.FileService,
        "resolve_session_for_transcript_path",
        lambda _p, _s: ("slug-2", "run-2"),
    )
    apply_transcript_selection_context(ss, "/tmp/test.json")
    assert ss["selected_transcript_path"].endswith("test.json")
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


def test_normalize_navigation_context_ignores_non_json_paths() -> None:
    ss = {"selected_transcript_path": "/tmp/not_a_transcript.txt"}
    changed = normalize_navigation_context_from_session(ss)
    assert changed is False
    assert "subject_type" not in ss
    assert "subject_id" not in ss


def test_page_hydration_gate_follows_required_context_only() -> None:
    assert page_requires_workspace_hydration("Home") is False
    assert page_requires_workspace_hydration("Library") is False
    assert page_requires_workspace_hydration("Search") is False
    assert page_requires_workspace_hydration("Statistics") is False
    assert page_requires_workspace_hydration("Settings") is False
    assert page_requires_workspace_hydration("Charts") is True
    assert page_requires_workspace_hydration("Overview") is True
    assert page_requires_workspace_hydration("Transcript") is True


def test_unknown_page_spec_is_non_hydrating() -> None:
    spec = get_page_spec("Totally Unknown Page")
    assert spec.required_context == "none"
    assert page_requires_workspace_hydration("Totally Unknown Page") is False


def test_build_prerequisites_matches_page_specs() -> None:
    from transcriptx.web.navigation import PAGE_SPECS

    prereqs = build_prerequisites()
    for spec in PAGE_SPECS:
        prereq = prereqs[spec.key]
        assert prereq.required_context == spec.required_context
        assert prereq.allowed_fallback == spec.allowed_fallback
        assert prereq.may_mutate_context == spec.may_mutate_context


def test_session_only_context_readiness_is_session_backed() -> None:
    ss = {
        "subject_type": "transcript",
        "subject_id": "slug-1",
        "run_id": "run-1",
    }
    readiness = session_only_context_readiness(ss)
    assert readiness["subject_ready"] is True
    assert readiness["run_scoped_ready"] is True
    assert readiness["transcript_ready"] is True
