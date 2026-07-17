"""Unit tests for search_service pure matching helpers."""

from __future__ import annotations

import pytest

from transcriptx.web.services.search_service import (
    _find_spans,
    _is_phrase_match,
    _is_word_boundary_match,
    _normalize,
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
