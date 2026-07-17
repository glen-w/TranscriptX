"""Expanded search_service tests: index, ranking, fuzzy gates, backend."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import List

import pytest

from transcriptx.web.models.search import (
    SearchFilters,
    SearchResult,
    SegmentRef,
    TranscriptRef,
)
from transcriptx.web.services.search_service import (
    FileSearchBackend,
    SearchService,
    _TranscriptIndex,
    _build_transcript_index,
    _resolve_transcript_mtime,
)


def _result(
    *,
    text: str,
    spans: List[tuple[int, int]],
    speaker: str = "Unknown",
    title: str = "demo",
    slug: str = "slug",
    run_id: str = "run1",
    index: int = 0,
) -> SearchResult:
    named = speaker not in ("", "Unknown")
    return SearchResult(
        segment_ref=SegmentRef(
            transcript_ref=TranscriptRef(
                session_slug=slug,
                run_id=run_id,
                transcript_slug=title,
            ),
            primary_locator="index",
            segment_index=index,
        ),
        transcript_title=title,
        session_slug=slug,
        run_id=run_id,
        segment_id=None,
        segment_index=index,
        segment_text=text,
        match_spans=spans,
        speaker_name=speaker,
        speaker_is_named=named,
        start_time=0.0,
        end_time=1.0,
    )


def _patch_backend_index(monkeypatch, mod, *, sessions, indexes_by_name) -> None:
    monkeypatch.setattr(
        mod,
        "cached_list_available_sessions",
        lambda: [{"name": n} for n in sessions],
    )
    monkeypatch.setattr(mod, "_resolve_session_path_for_search", lambda n: f"/path/{n}")
    monkeypatch.setattr(mod, "_resolve_transcript_mtime", lambda _n: None)
    monkeypatch.setattr(
        mod,
        "_build_transcript_index",
        lambda session_name, *_a, **_k: indexes_by_name.get(session_name),
    )
    monkeypatch.setattr(
        mod, "resolve_speaker_names_from_sidecars", lambda segs, _p: segs
    )


@pytest.mark.unit
def test_resolve_transcript_mtime_prefers_filesystem_stat(
    monkeypatch, tmp_path: Path
) -> None:
    import transcriptx.web.services.search_service as mod

    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    expected = float(transcript.stat().st_mtime)

    monkeypatch.setattr(
        mod.FileService,
        "resolve_transcript_path",
        lambda _name: transcript,
    )

    def _boom(_name: str):
        raise AssertionError("should not load transcript when path exists")

    monkeypatch.setattr(mod.FileService, "load_transcript_by_session", _boom)
    assert _resolve_transcript_mtime("slug/run") == expected


@pytest.mark.unit
def test_resolve_transcript_mtime_from_source(monkeypatch) -> None:
    import transcriptx.web.services.search_service as mod

    monkeypatch.setattr(
        mod.FileService,
        "resolve_transcript_path",
        lambda _name: None,
    )
    monkeypatch.setattr(
        mod.FileService,
        "load_transcript_by_session",
        lambda _name: {"source": {"file_mtime": 12.5}},
    )
    assert _resolve_transcript_mtime("slug/run") == 12.5


@pytest.mark.unit
def test_resolve_transcript_mtime_missing_or_bad(monkeypatch) -> None:
    import transcriptx.web.services.search_service as mod

    monkeypatch.setattr(
        mod.FileService,
        "resolve_transcript_path",
        lambda _name: None,
    )
    monkeypatch.setattr(
        mod.FileService, "load_transcript_by_session", lambda _name: None
    )
    assert _resolve_transcript_mtime("x") is None

    monkeypatch.setattr(
        mod.FileService,
        "load_transcript_by_session",
        lambda _name: {"source": {"file_mtime": "nope"}},
    )
    assert _resolve_transcript_mtime("x") is None


@pytest.mark.unit
def test_build_transcript_index_builds_vocab_and_blob(monkeypatch) -> None:
    import transcriptx.web.services.search_service as mod

    monkeypatch.setattr(
        mod.FileService,
        "load_transcript_by_session",
        lambda _name: {
            "source": {"original_path": "/data/meeting.json"},
            "segments": [
                {"text": "Hello world"},
                {"text": "Meeting notes"},
                {"text": 123},
            ],
        },
    )
    # Bypass Streamlit cache wrapper when present
    build = getattr(_build_transcript_index, "__wrapped__", _build_transcript_index)
    index = build("slug/run1", "/data/meeting.json", 1.0)
    assert index is not None
    assert index.transcript_slug == "meeting"
    assert "hello" in index.text_blob
    assert "meeting" in index.vocab
    assert "notes" in index.vocab
    assert len(index.segments) == 3


@pytest.mark.unit
def test_build_transcript_index_returns_none_without_segments(monkeypatch) -> None:
    import transcriptx.web.services.search_service as mod

    monkeypatch.setattr(
        mod.FileService,
        "load_transcript_by_session",
        lambda _name: {"segments": "bad"},
    )
    build = getattr(_build_transcript_index, "__wrapped__", _build_transcript_index)
    assert build("slug/run1", "p", None) is None


@pytest.mark.unit
def test_rank_results_prefers_word_boundary_and_named_speaker() -> None:
    svc = SearchService()
    boundary = _result(text="the cat sat", spans=[(4, 7)], speaker="Alice")
    embedded = _result(text="catalog entry", spans=[(0, 3)], speaker="Unknown", index=1)
    ranked = svc._rank_results([embedded, boundary], "cat")
    assert ranked[0].segment_text == "the cat sat"
    assert ranked[0].speaker_is_named is True


@pytest.mark.unit
def test_rank_results_prefers_phrase_over_token_and() -> None:
    svc = SearchService()
    phrase = _result(text="alpha beta together", spans=[(0, 10)], index=0)
    token_and = _result(text="beta then alpha", spans=[(0, 4), (10, 15)], index=1)
    ranked = svc._rank_results([token_and, phrase], "alpha beta")
    assert ranked[0].segment_text == "alpha beta together"


@pytest.mark.unit
def test_search_all_skips_fuzzy_when_query_short(monkeypatch) -> None:
    svc = SearchService()
    monkeypatch.setattr(
        svc,
        "_select_backend",
        lambda: SimpleNamespace(search_substring=lambda q, f=None: ([], 0)),
    )
    response = svc.search_all_transcripts("abc", enable_fuzzy=True)
    assert response.fuzzy_ran is False
    assert response.fuzzy_reason == "query too short"


@pytest.mark.unit
def test_search_all_skips_fuzzy_when_enough_substring(monkeypatch) -> None:
    svc = SearchService()
    many = [_result(text=f"query hit {i}", spans=[(0, 5)], index=i) for i in range(10)]
    monkeypatch.setattr(
        svc,
        "_select_backend",
        lambda: SimpleNamespace(search_substring=lambda q, f=None: (many, len(many))),
    )
    response = svc.search_all_transcripts("query", enable_fuzzy=True)
    assert response.fuzzy_ran is False
    assert response.fuzzy_reason == "sufficient substring results"
    assert response.total_shown == 10


@pytest.mark.unit
def test_search_all_runs_fuzzy_when_few_hits(monkeypatch) -> None:
    svc = SearchService()
    few = [_result(text="query once", spans=[(0, 5)])]
    fuzzy = [_result(text="quase match", spans=[], index=1)]
    monkeypatch.setattr(
        svc,
        "_select_backend",
        lambda: SimpleNamespace(search_substring=lambda q, f=None: (few, 1)),
    )
    monkeypatch.setattr(svc, "_select_candidate_transcripts", lambda _q, _f=None: ["c"])
    monkeypatch.setattr(svc, "_fuzzy_search", lambda *_a, **_k: fuzzy)
    response = svc.search_all_transcripts("query", enable_fuzzy=True)
    assert response.fuzzy_ran is True
    assert response.fuzzy_reason == "few substring results"
    assert len(response.fuzzy_results) == 1


@pytest.mark.unit
def test_select_candidate_transcripts_requires_token_overlap(monkeypatch) -> None:
    import transcriptx.web.services.search_service as mod

    hit = _TranscriptIndex(
        session_name="slug/run1",
        transcript_slug="hit",
        segments=[],
        text_blob="alpha beta gamma",
        vocab={"alpha", "beta", "gamma"},
    )
    miss = _TranscriptIndex(
        session_name="slug/run2",
        transcript_slug="miss",
        segments=[],
        text_blob="other words here",
        vocab={"other", "words", "here"},
    )
    monkeypatch.setattr(
        mod,
        "cached_list_available_sessions",
        lambda: [{"name": "slug/run1"}, {"name": "slug/run2"}, {"name": ""}],
    )
    monkeypatch.setattr(mod, "_resolve_session_path_for_search", lambda n: n)
    monkeypatch.setattr(mod, "_resolve_transcript_mtime", lambda _n: None)

    def _build(session_name, *_a, **_k):
        return hit if session_name.endswith("run1") else miss

    monkeypatch.setattr(mod, "_build_transcript_index", _build)
    svc = SearchService()
    assert svc._select_candidate_transcripts("xy") == []
    assert [c.transcript_slug for c in svc._select_candidate_transcripts("alpha")] == [
        "hit"
    ]


@pytest.mark.unit
def test_select_candidate_transcripts_respects_session_filters(monkeypatch) -> None:
    import transcriptx.web.services.search_service as mod

    a = _TranscriptIndex(
        session_name="alpha/run1",
        transcript_slug="a",
        segments=[],
        text_blob="alpha beta",
        vocab={"alpha", "beta"},
    )
    b = _TranscriptIndex(
        session_name="beta/run1",
        transcript_slug="b",
        segments=[],
        text_blob="alpha beta",
        vocab={"alpha", "beta"},
    )
    monkeypatch.setattr(
        mod,
        "cached_list_available_sessions",
        lambda: [{"name": "alpha/run1"}, {"name": "beta/run1"}],
    )
    monkeypatch.setattr(mod, "_resolve_session_path_for_search", lambda n: n)
    monkeypatch.setattr(mod, "_resolve_transcript_mtime", lambda _n: None)
    monkeypatch.setattr(
        mod,
        "_build_transcript_index",
        lambda session_name, *_a, **_k: a if session_name.startswith("alpha") else b,
    )
    svc = SearchService()
    filters = SearchFilters(session_slugs=["alpha"])
    assert [
        c.session_name for c in svc._select_candidate_transcripts("alpha", filters)
    ] == ["alpha/run1"]


@pytest.mark.unit
def test_file_search_backend_substring_match(monkeypatch) -> None:
    import transcriptx.web.services.search_service as mod

    index = _TranscriptIndex(
        session_name="slug/run1",
        transcript_slug="demo",
        segments=[
            {
                "text": "Hello searchable world",
                "speaker": "A",
                "start": 0.0,
                "end": 1.0,
            },
            {"text": "nope", "speaker": "B", "start": 1.0, "end": 2.0},
        ],
        text_blob="hello searchable world nope",
        vocab={"hello", "searchable", "world", "nope"},
    )
    _patch_backend_index(
        monkeypatch, mod, sessions=["slug/run1"], indexes_by_name={"slug/run1": index}
    )

    results, total = FileSearchBackend().search_substring("searchable")
    assert total == 1
    assert results[0].segment_text == "Hello searchable world"
    assert results[0].match_spans == [(6, 16)]
    assert results[0].speaker_name == "A"
    assert results[0].context_before is None
    assert results[0].context_after == "nope"


@pytest.mark.unit
def test_file_search_backend_respects_session_and_speaker_filters(monkeypatch) -> None:
    import transcriptx.web.services.search_service as mod

    keep = _TranscriptIndex(
        session_name="keep/run1",
        transcript_slug="keep",
        segments=[
            {
                "text": "hello searchable",
                "speaker": "Alice",
                "start": 0.0,
                "end": 1.0,
            },
            {
                "text": "hello searchable",
                "speaker": "Bob",
                "start": 1.0,
                "end": 2.0,
            },
        ],
        text_blob="hello searchable hello searchable",
        vocab={"hello", "searchable"},
    )
    drop = _TranscriptIndex(
        session_name="drop/run1",
        transcript_slug="drop",
        segments=[
            {
                "text": "hello searchable",
                "speaker": "Alice",
                "start": 0.0,
                "end": 1.0,
            },
        ],
        text_blob="hello searchable",
        vocab={"hello", "searchable"},
    )
    _patch_backend_index(
        monkeypatch,
        mod,
        sessions=["keep/run1", "drop/run1"],
        indexes_by_name={"keep/run1": keep, "drop/run1": drop},
    )

    filters = SearchFilters(session_slugs=["keep"], speaker_keys=["Alice"])
    results, total = FileSearchBackend().search_substring("searchable", filters)
    assert total == 1
    assert results[0].session_slug == "keep"
    assert results[0].speaker_name == "Alice"


@pytest.mark.unit
def test_file_search_backend_token_and_match(monkeypatch) -> None:
    import transcriptx.web.services.search_service as mod

    index = _TranscriptIndex(
        session_name="slug/run1",
        transcript_slug="demo",
        segments=[
            {
                "text": "gamma then alpha later",
                "speaker": "A",
                "start": 0.0,
                "end": 1.0,
            },
            {
                "text": "only alpha",
                "speaker": "A",
                "start": 1.0,
                "end": 2.0,
            },
        ],
        text_blob="gamma then alpha later only alpha",
        vocab={"gamma", "then", "alpha", "later", "only"},
    )
    _patch_backend_index(
        monkeypatch, mod, sessions=["slug/run1"], indexes_by_name={"slug/run1": index}
    )

    results, total = FileSearchBackend().search_substring("alpha gamma")
    assert total == 1
    assert results[0].segment_text == "gamma then alpha later"
    assert len(results[0].match_spans) >= 2


@pytest.mark.unit
def test_file_search_backend_attaches_neighbor_context(monkeypatch) -> None:
    import transcriptx.web.services.search_service as mod

    index = _TranscriptIndex(
        session_name="slug/run1",
        transcript_slug="demo",
        segments=[
            {"text": "before line", "speaker": "A", "start": 0.0, "end": 1.0},
            {"text": "hit searchable", "speaker": "A", "start": 1.0, "end": 2.0},
            {"text": "after line", "speaker": "A", "start": 2.0, "end": 3.0},
        ],
        text_blob="before line hit searchable after line",
        vocab={"before", "line", "hit", "searchable", "after"},
    )
    _patch_backend_index(
        monkeypatch, mod, sessions=["slug/run1"], indexes_by_name={"slug/run1": index}
    )

    results, _total = FileSearchBackend().search_substring("searchable")
    assert len(results) == 1
    assert results[0].context_before == "before line"
    assert results[0].context_after == "after line"
    assert results[0].context_indices == (0, 2)


@pytest.mark.unit
def test_fuzzy_search_respects_speaker_filter(monkeypatch) -> None:
    import transcriptx.web.services.search_service as mod

    index = _TranscriptIndex(
        session_name="slug/run1",
        transcript_slug="demo",
        segments=[
            {"text": "almost query here", "speaker": "Alice", "start": 0.0, "end": 1.0},
            {"text": "almost query here", "speaker": "Bob", "start": 1.0, "end": 2.0},
        ],
        text_blob="almost query here almost query here",
        vocab={"almost", "query", "here"},
    )
    monkeypatch.setattr(mod, "_resolve_session_path_for_search", lambda n: f"/p/{n}")
    monkeypatch.setattr(
        mod, "resolve_speaker_names_from_sidecars", lambda segs, _p: segs
    )
    svc = SearchService()
    filters = SearchFilters(speaker_keys=["Alice"])
    results = svc._fuzzy_search([index], "query", threshold=50.0, filters=filters)
    assert len(results) == 1
    assert results[0].speaker_name == "Alice"
    # Fuzzy path must resolve speakers via filesystem path, not session_name alone.
    # Covered by monkeypatched resolve_speaker_names receiving /p/slug/run1.


@pytest.mark.unit
def test_fuzzy_search_returns_empty_without_rapidfuzz(monkeypatch) -> None:
    import builtins

    svc = SearchService()
    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "rapidfuzz" or name.startswith("rapidfuzz."):
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    index = _TranscriptIndex(
        session_name="slug/run1",
        transcript_slug="demo",
        segments=[{"text": "almost query"}],
        text_blob="almost query",
        vocab={"almost", "query"},
    )
    assert svc._fuzzy_search([index], "query") == []
