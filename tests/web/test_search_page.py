"""Search page thin Streamlit orchestration contracts (L3)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from transcriptx.web.models.search import (
    SearchFilters,
    SearchResponse,
    SearchResult,
    SegmentRef,
    TranscriptRef,
)
from tests.web.streamlit_doubles import DummyHomeStreamlit


def _make_result(text: str = "hello world") -> SearchResult:
    tref = TranscriptRef(
        session_slug="sess-1", run_id="run-1", transcript_slug="Meeting"
    )
    sref = SegmentRef(
        transcript_ref=tref,
        primary_locator="index",
        segment_id=0,
        segment_index=0,
        timecode=0.0,
    )
    return SearchResult(
        segment_ref=sref,
        transcript_title="Meeting",
        session_slug="sess-1",
        run_id="run-1",
        segment_id=0,
        segment_index=0,
        segment_text=text,
        match_spans=[(0, 5)],
        speaker_name="A",
        speaker_is_named=True,
        start_time=0.0,
        end_time=1.0,
        context_before="",
        context_after="",
    )


class _SearchStreamlit(DummyHomeStreamlit):
    session_state: dict = {}
    query: str = ""
    scope: str = "All transcripts"
    fuzzy: bool = True
    first_match: bool = True
    speaker: str = "All speakers"
    captions: list[str] = []
    rerun_calls: int = 0

    @classmethod
    def reset(cls) -> None:
        cls.session_state = {}
        cls.query = ""
        cls.scope = "All transcripts"
        cls.fuzzy = True
        cls.first_match = True
        cls.speaker = "All speakers"
        cls.captions = []
        cls.rerun_calls = 0

    @staticmethod
    def fragment(fn=None, **_kwargs):
        if fn is None:

            def _decorator(f):
                return f

            return _decorator
        return fn

    @classmethod
    def text_input(cls, *_a, **_k):
        return cls.query

    @classmethod
    def radio(cls, _label, options, index=0, **_kwargs):
        if cls.scope in options:
            return cls.scope
        return options[index]

    @classmethod
    def checkbox(cls, label, value=False, key=None, **_kwargs):
        if key == "global_search_fuzzy":
            return cls.fuzzy
        if key == "global_search_first_match_only":
            return cls.first_match
        return value

    @classmethod
    def selectbox(cls, *_a, **_k):
        return cls.speaker

    @classmethod
    def caption(cls, text, **_kwargs):
        cls.captions.append(str(text))

    @staticmethod
    def spinner(_msg):
        return DummyHomeStreamlit.expander()

    @classmethod
    def rerun(cls):
        cls.rerun_calls += 1


def _patch_search(monkeypatch, mod) -> list:
    empty_calls: list = []
    _SearchStreamlit.reset()
    monkeypatch.setattr(mod, "st", _SearchStreamlit)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod,
        "render_empty_state",
        lambda *args, **kwargs: empty_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(mod, "get_speakers_from_transcripts", lambda *_a, **_k: [])
    monkeypatch.setattr(
        mod, "time", SimpleNamespace(time=lambda: 1_000.0, sleep=lambda *_a: None)
    )
    return empty_calls


@pytest.mark.unit
def test_search_short_query_skips_search(monkeypatch) -> None:
    import transcriptx.web.page_modules.search as mod

    empty_calls = _patch_search(monkeypatch, mod)
    search_mock = MagicMock()
    monkeypatch.setattr(mod, "SearchService", lambda: search_mock)
    _SearchStreamlit.query = "ab"
    _SearchStreamlit.session_state = {
        "global_search_last_change": 0.0,
        "global_search_last_query": "ab",
    }

    frag = mod._search_interaction_fragment.__wrapped__
    frag()

    search_mock.search_all_transcripts.assert_not_called()
    assert empty_calls == []


@pytest.mark.unit
def test_search_empty_results_renders_empty_state(monkeypatch) -> None:
    import transcriptx.web.page_modules.search as mod

    empty_calls = _patch_search(monkeypatch, mod)
    response = SearchResponse(
        substring_results=[],
        fuzzy_results=[],
        total_found=0,
        total_shown=0,
        fuzzy_ran=False,
    )
    search_mock = MagicMock()
    search_mock.search_all_transcripts.return_value = response
    monkeypatch.setattr(mod, "SearchService", lambda: search_mock)
    _SearchStreamlit.query = "hello"
    _SearchStreamlit.session_state = {
        "global_search_last_change": 0.0,
        "global_search_last_query": "hello",
    }

    frag = mod._search_interaction_fragment.__wrapped__
    frag()

    search_mock.search_all_transcripts.assert_called_once()
    assert empty_calls
    assert empty_calls[0][0][0] == "no_results_yet"
    assert "No matches found" in empty_calls[0][0][1]


@pytest.mark.unit
def test_search_results_render_section(monkeypatch) -> None:
    import transcriptx.web.page_modules.search as mod

    _patch_search(monkeypatch, mod)
    result = _make_result()
    response = SearchResponse(
        substring_results=[result],
        fuzzy_results=[],
        total_found=1,
        total_shown=1,
        fuzzy_ran=False,
    )
    search_mock = MagicMock()
    search_mock.search_all_transcripts.return_value = response
    monkeypatch.setattr(mod, "SearchService", lambda: search_mock)
    section_calls: list = []
    monkeypatch.setattr(
        mod,
        "_render_results_section",
        lambda *args, **kwargs: section_calls.append(args),
    )
    _SearchStreamlit.query = "hello"
    _SearchStreamlit.session_state = {
        "global_search_last_change": 0.0,
        "global_search_last_query": "hello",
    }

    frag = mod._search_interaction_fragment.__wrapped__
    frag()

    assert section_calls
    assert section_calls[0][0] == "Matches"
    assert section_calls[0][1] == [result]


@pytest.mark.unit
def test_search_current_transcript_scope_passes_session_slug(monkeypatch) -> None:
    import transcriptx.web.page_modules.search as mod

    _patch_search(monkeypatch, mod)
    response = SearchResponse(
        substring_results=[],
        fuzzy_results=[],
        total_found=0,
        total_shown=0,
        fuzzy_ran=False,
    )
    search_mock = MagicMock()
    search_mock.search_all_transcripts.return_value = response
    monkeypatch.setattr(mod, "SearchService", lambda: search_mock)
    monkeypatch.setattr(
        mod.SubjectService,
        "resolve_current_subject",
        lambda _ss: SimpleNamespace(subject_type="transcript", subject_id="slug-a"),
    )
    _SearchStreamlit.query = "hello"
    _SearchStreamlit.scope = "Current transcript"
    _SearchStreamlit.session_state = {
        "global_search_last_change": 0.0,
        "global_search_last_query": "hello",
    }

    frag = mod._search_interaction_fragment.__wrapped__
    frag()

    assert search_mock.search_all_transcripts.called
    filters: SearchFilters = search_mock.search_all_transcripts.call_args[0][1]
    assert filters.session_slugs == ["slug-a"]


@pytest.mark.unit
def test_search_group_subject_does_not_scope_session_slugs(monkeypatch) -> None:
    """E4: group subject + Current transcript scope does not set session_slugs."""
    import transcriptx.web.page_modules.search as mod

    _patch_search(monkeypatch, mod)
    response = SearchResponse(
        substring_results=[],
        fuzzy_results=[],
        total_found=0,
        total_shown=0,
        fuzzy_ran=False,
    )
    search_mock = MagicMock()
    search_mock.search_all_transcripts.return_value = response
    monkeypatch.setattr(mod, "SearchService", lambda: search_mock)
    monkeypatch.setattr(
        mod.SubjectService,
        "resolve_current_subject",
        lambda _ss: SimpleNamespace(subject_type="group", subject_id="g-1"),
    )
    _SearchStreamlit.query = "hello"
    _SearchStreamlit.scope = "Current transcript"
    _SearchStreamlit.session_state = {
        "global_search_last_change": 0.0,
        "global_search_last_query": "hello",
    }

    frag = mod._search_interaction_fragment.__wrapped__
    frag()

    filters: SearchFilters = search_mock.search_all_transcripts.call_args[0][1]
    assert filters.session_slugs is None


@pytest.mark.unit
def test_render_search_invokes_fragment(monkeypatch) -> None:
    import transcriptx.web.page_modules.search as mod

    _patch_search(monkeypatch, mod)
    calls: list = []
    monkeypatch.setattr(mod, "_search_interaction_fragment", lambda: calls.append(True))

    mod.render_search()

    assert calls
