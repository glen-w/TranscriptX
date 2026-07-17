"""Unit tests for search_service pure matching helpers."""

from __future__ import annotations

import pytest

from transcriptx.web.models.search import SearchFilters
from transcriptx.web.services.search_service import (
    _find_spans,
    _is_phrase_match,
    _is_word_boundary_match,
    _match_segment_text,
    _normalize,
    _segment_matches_speaker_filters,
    _session_matches_filters,
    _tokenize,
)


@pytest.mark.unit
class TestSearchNormalizeTokenize:
    def test_normalize_lowercases(self) -> None:
        assert _normalize("Hello WORLD") == "hello world"

    def test_tokenize_drops_short_tokens(self) -> None:
        assert _tokenize("a to the meeting notes") == ["the", "meeting", "notes"]

    def test_tokenize_splits_on_non_word(self) -> None:
        assert _tokenize("alpha-beta,gamma!") == ["alpha", "beta", "gamma"]

    def test_tokenize_empty_query(self) -> None:
        assert _tokenize("") == []
        assert _tokenize("ab cd") == []


@pytest.mark.unit
class TestSearchSpansAndMatching:
    def test_find_spans_empty_query(self) -> None:
        assert _find_spans("hello world", "") == []

    def test_find_spans_case_insensitive_non_overlapping(self) -> None:
        assert _find_spans("Foo foo FOO", "foo") == [(0, 3), (4, 7), (8, 11)]

    def test_word_boundary_requires_whole_word(self) -> None:
        assert _is_word_boundary_match("catalog", "cat") is False
        assert _is_word_boundary_match("the cat sat", "cat") is True

    def test_word_boundary_empty_query(self) -> None:
        assert _is_word_boundary_match("text", "") is False

    def test_phrase_match_substring(self) -> None:
        assert _is_phrase_match("Hello World", "lo wo") is True
        assert _is_phrase_match("Hello World", "xyz") is False

    def test_match_segment_phrase_preferred(self) -> None:
        spans, is_phrase = _match_segment_text("alpha beta gamma", "alpha beta")
        assert is_phrase is True
        assert spans == [(0, 10)]

    def test_match_segment_token_and_when_phrase_fails(self) -> None:
        matched = _match_segment_text("gamma then alpha", "alpha gamma")
        assert matched is not None
        spans, is_phrase = matched
        assert is_phrase is False
        assert len(spans) >= 2

    def test_match_segment_rejects_partial_token_and(self) -> None:
        assert _match_segment_text("only alpha here", "alpha gamma") is None

    def test_match_segment_single_token_uses_substring(self) -> None:
        # Single-token queries still use contiguous substring (existing phrase path).
        spans, is_phrase = _match_segment_text("catalog", "cat")
        assert is_phrase is True
        assert spans == [(0, 3)]
        assert _match_segment_text("nope", "cat") is None


@pytest.mark.unit
class TestSearchFiltersHelpers:
    def test_session_matches_filters_by_slug(self) -> None:
        filters = SearchFilters(session_slugs=["alpha"])
        assert _session_matches_filters("alpha/run1", filters) is True
        assert _session_matches_filters("beta/run1", filters) is False
        assert _session_matches_filters("alpha/run1", None) is True
        assert _session_matches_filters("alpha/run1", SearchFilters()) is True

    def test_segment_matches_speaker_filters(self) -> None:
        filters = SearchFilters(speaker_keys=["Alice"])
        assert (
            _segment_matches_speaker_filters({"speaker_display": "Alice"}, filters)
            is True
        )
        assert _segment_matches_speaker_filters({"speaker": "Bob"}, filters) is False
        assert _segment_matches_speaker_filters({"speaker": "Bob"}, None) is True
