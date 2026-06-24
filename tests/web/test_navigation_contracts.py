from __future__ import annotations

from pathlib import Path

from transcriptx.app.models.metadata import TranscriptMetadata
from transcriptx.web.navigation import (
    PagePrerequisite,
    apply_library_rename_navigation,
    apply_transcript_selection_context,
    consume_library_transcript_nav,
    evaluate_page_access,
    library_transcript_index,
    normalize_navigation_context_from_session,
)
from transcriptx.web.sidebar_state import (
    SidebarSelectionResult,
    apply_sidebar_selection,
    apply_transitional_sidebar_backfill,
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


def test_sidebar_noop_backfill_does_not_rewrite_canonical_context() -> None:
    ss = {
        "subject_type": "transcript",
        "subject_id": "slug-1",
        "run_id": "run-1",
    }
    apply_transitional_sidebar_backfill(ss, prioritize_view=True)
    before = (ss["subject_type"], ss["subject_id"], ss["run_id"])
    apply_transitional_sidebar_backfill(ss, prioritize_view=True)
    after = (ss["subject_type"], ss["subject_id"], ss["run_id"])
    assert before == after


def test_page_prerequisite_access_uses_readiness_flags() -> None:
    prereqs = {"Overview": PagePrerequisite("run_scoped", "home")}
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


def test_apply_transitional_sidebar_backfill_promotes_view_when_prioritize_toggles_true() -> (
    None
):
    from transcriptx.web.state import (
        TX_NAV_EXPANDER_VIEW,
        TX_NAV_EXPANDER_WORKFLOW,
        TX_NAV_PREV_SHOULD_PRIORITIZE_VIEW,
        TX_NAV_SIDEBAR_SEEDED,
    )

    ss = {
        TX_NAV_SIDEBAR_SEEDED: True,
        TX_NAV_PREV_SHOULD_PRIORITIZE_VIEW: False,
        TX_NAV_EXPANDER_WORKFLOW: True,
        TX_NAV_EXPANDER_VIEW: False,
    }
    apply_transitional_sidebar_backfill(ss, prioritize_view=True)
    assert ss[TX_NAV_EXPANDER_VIEW] is True
    assert ss[TX_NAV_EXPANDER_WORKFLOW] is False
