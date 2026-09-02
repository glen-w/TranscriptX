"""Tests for transcript page refactor contracts."""

from __future__ import annotations

from contextlib import contextmanager

import transcriptx.web.page_modules.transcript as mod
import transcriptx.web.transcript_navigation as transcript_nav
from transcriptx.web.models.search import SegmentRef, TranscriptRef
from transcriptx.web.state import (
    NAV_REQUEST_KEY,
    PAGE_KEY,
    RUN_ID_KEY,
    RUN_SELECTOR_KEY,
    SUBJECT_ID_KEY,
    SUBJECT_ID_SELECTOR_KEY,
    SUBJECT_TYPE_KEY,
)
from transcriptx.web.transcript_view_state import transcript_context_result


def test_navigate_to_segment_sets_canonical_state_and_reruns(monkeypatch) -> None:
    state: dict = {
        SUBJECT_ID_SELECTOR_KEY: "",
        RUN_SELECTOR_KEY: "stale",
    }
    called = {"rerun": 0}

    class _DummySt:
        session_state = state

        @staticmethod
        def rerun():
            called["rerun"] += 1

    monkeypatch.setattr(transcript_nav, "st", _DummySt)
    ref = SegmentRef(
        transcript_ref=TranscriptRef(session_slug="slug", run_id="run1"),
        primary_locator="index",
        segment_index=7,
    )

    mod.navigate_to_segment(ref, highlight_query="hello")

    assert state[SUBJECT_TYPE_KEY] == "transcript"
    assert state[SUBJECT_ID_KEY] == "slug"
    assert state[RUN_ID_KEY] == "run1"
    assert state[PAGE_KEY] == "Transcript"
    assert state[NAV_REQUEST_KEY].highlight_query == "hello"
    assert state[SUBJECT_ID_SELECTOR_KEY] == "slug"
    assert state[RUN_SELECTOR_KEY] == "run1"
    assert called["rerun"] == 1


def test_render_transcript_controls_contract(monkeypatch) -> None:
    markdown_calls: list[str] = []
    state = {"timestamp_format": "seconds"}
    checkbox_keys: list[str] = []

    class _DummySt:
        session_state = state

        @staticmethod
        def markdown(text, unsafe_allow_html=False):
            markdown_calls.append(text)

        @staticmethod
        def text_input(_label, key, help=None):
            assert key == "transcript_search"
            assert help is None or isinstance(help, str)
            return "needle"

        @staticmethod
        def checkbox(_label, key, help=None):
            checkbox_keys.append(key)
            return key == "show_timestamps"

    monkeypatch.setattr(mod, "st", _DummySt)
    result = mod._render_transcript_controls()
    assert result.search_text == "needle"
    assert result.show_timestamps is True
    assert result.show_unnamed_speakers is False
    assert result.format_key == "seconds"
    assert checkbox_keys == ["show_timestamps", "show_unnamed_speakers"]
    # Empty markdown wrappers cannot contain Streamlit widgets and paint as a
    # thick white bar under dark chrome — controls must not emit them.
    assert markdown_calls == []


def test_resolve_and_prepare_segments_only_enriches_when_non_empty(monkeypatch) -> None:
    called = {"count": 0}

    def _fake_resolve(segments, selected):
        called["count"] += 1
        assert selected == "slug/run"
        return [{"text": "resolved"}]

    monkeypatch.setattr(mod, "resolve_speaker_names_from_db", _fake_resolve)
    assert mod._resolve_and_prepare_segments({"segments": []}, "slug/run") == []
    assert called["count"] == 0
    out = mod._resolve_and_prepare_segments({"segments": [{"text": "x"}]}, "slug/run")
    assert called["count"] == 1
    assert out == [{"text": "resolved"}]


def test_render_transcript_viewer_does_not_consume_nav_request_on_empty_segments(
    monkeypatch,
) -> None:
    state = {mod.NAV_REQUEST_KEY: "keep-me"}

    class _DummySt:
        session_state = state

        @staticmethod
        @contextmanager
        def spinner(_msg):
            yield

        @staticmethod
        def error(_msg):
            return None

        @staticmethod
        def exception(_exc):
            return None

        @staticmethod
        def divider():
            return None

    monkeypatch.setattr(mod, "st", _DummySt)
    monkeypatch.setattr(mod, "render_page_shell", lambda *a, **k: None)
    monkeypatch.setattr(mod, "_render_metadata_metrics", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "render_download_row", lambda *a, **k: None)
    monkeypatch.setattr(mod, "render_empty_state", lambda *a, **k: None)
    monkeypatch.setattr(
        mod,
        "resolve_viewer_preflight",
        lambda *a, **k: mod.ViewerPreflight(
            status="ok",
            context_result=transcript_context_result(
                ok=True,
                session_slug="slug",
                run_id="run1",
                run_root=__import__("pathlib").Path("/tmp"),
            ),
        ),
    )
    monkeypatch.setattr(
        mod,
        "load_transcript_with_path_by_session",
        lambda _s: ({"segments": []}, __import__("pathlib").Path("/tmp/t.json")),
    )
    monkeypatch.setattr(
        mod,
        "resolve_transcript_artifacts",
        lambda **_k: __import__("types").SimpleNamespace(
            txt_file=None, csv_file=None, srt_file=None, vtt_file=None, json_file=None
        ),
    )
    monkeypatch.setattr(
        mod,
        "consume_nav_request",
        lambda _s: (_ for _ in ()).throw(
            AssertionError("consume_nav_request should not be called when no segments")
        ),
    )

    mod.render_transcript_viewer()
    assert state[mod.NAV_REQUEST_KEY] == "keep-me"


def test_transcript_tab_nav_includes_chapters_when_available(monkeypatch) -> None:
    state: dict = {"transcript_viewer_tab": "turns"}

    class _DummySt:
        session_state = state

        @staticmethod
        def segmented_control(_label, options, key, label_visibility="collapsed"):
            assert "Chapters" in options
            assert key == "transcript_viewer_tab_control"
            return "Chapters"

    monkeypatch.setattr(mod, "st", _DummySt)
    selected = mod._render_transcript_tab_nav(has_chapters=True)
    assert selected == "chapters"
    assert state["transcript_viewer_tab"] == "chapters"


def test_transcript_tab_nav_omits_chapters_without_rows(monkeypatch) -> None:
    state: dict = {"transcript_viewer_tab": "chapters"}

    class _DummySt:
        session_state = state

        @staticmethod
        def segmented_control(_label, options, key, label_visibility="collapsed"):
            assert "Chapters" not in options
            return "Turns"

    monkeypatch.setattr(mod, "st", _DummySt)
    selected = mod._render_transcript_tab_nav(has_chapters=False)
    assert selected == "turns"
    assert state["transcript_viewer_tab"] == "turns"


def test_chapters_panel_jump_queues_without_play(monkeypatch) -> None:
    from transcriptx.web.transcript_viewer.chapters import ChapterRow

    state: dict = {}
    captions: list[str] = []
    markdowns: list[str] = []
    reruns: list = []

    class _Col:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _DummySt:
        session_state = state

        @staticmethod
        def caption(text):
            captions.append(text)

        @staticmethod
        def markdown(text, **_k):
            markdowns.append(text)

        @staticmethod
        def columns(_spec):
            return (_Col(), _Col(), _Col(), _Col())

        @staticmethod
        def button(label, **_k):
            return label == "Jump"

        @staticmethod
        def rerun(*, scope=None):
            reruns.append(scope)

    row = ChapterRow(
        span_id="s1",
        index=0,
        title="Opening",
        time_start=0.0,
        time_end=12.0,
        viewer_target_source_index=3,
        leading_boundary_id=None,
        strength=None,
        summary="Brief",
    )
    monkeypatch.setattr(mod, "st", _DummySt)
    mod._render_chapters_panel([row])
    assert any("Opening" in m for m in markdowns)
    assert any("Brief" in c for c in captions)
    assert state["transcript_viewer_chapter_pending"] == {
        "jump_index": 3,
        "play": False,
    }
    assert reruns == ["fragment"]


def test_chapters_panel_empty_caption(monkeypatch) -> None:
    captions: list[str] = []

    class _DummySt:
        session_state: dict = {}

        @staticmethod
        def caption(text):
            captions.append(text)

    monkeypatch.setattr(mod, "st", _DummySt)
    mod._render_chapters_panel([])
    assert captions == ["No topic-shift chapters for this run."]


def test_chapters_panel_skips_redundant_keyword_caption(monkeypatch) -> None:
    from transcriptx.web.transcript_viewer.chapters import ChapterRow

    captions: list[str] = []
    markdowns: list[str] = []

    class _Col:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _DummySt:
        session_state: dict = {}

        @staticmethod
        def caption(text):
            captions.append(text)

        @staticmethod
        def markdown(text, **_k):
            markdowns.append(text)

        @staticmethod
        def columns(_spec):
            return (_Col(), _Col(), _Col(), _Col())

        @staticmethod
        def button(_label, **_k):
            return False

    # Title is first 4 hints; keywords include one extra — don't echo the list.
    keyword_built = ChapterRow(
        span_id="s1",
        index=0,
        title="Season · Club · Chronograph · Girls",
        time_start=60.0,
        time_end=3000.0,
        viewer_target_source_index=None,
        leading_boundary_id=None,
        strength=None,
        summary=None,
        keywords=(
            "Season",
            "Club",
            "Chronograph",
            "Girls",
            "Paris",
        ),
    )
    # Distinct LLM title — keywords remain useful secondary detail.
    llm_titled = ChapterRow(
        span_id="s2",
        index=1,
        title="Budget discussion",
        time_start=3000.0,
        time_end=3600.0,
        viewer_target_source_index=None,
        leading_boundary_id="b1",
        strength=0.2,
        summary=None,
        keywords=("Budget", "Finance", "Planning"),
    )
    monkeypatch.setattr(mod, "st", _DummySt)
    mod._render_chapters_panel([keyword_built, llm_titled])

    assert any("Season · Club · Chronograph · Girls" in m for m in markdowns)
    assert not any("Paris" in c for c in captions)
    assert any("Budget · Finance · Planning" in c for c in captions)
    assert any("strength 0.20" in c for c in captions)
