"""Unit tests for word ↔ char span mapping and ambiguous find."""

from __future__ import annotations

import pytest

from transcriptx.core.corrections.word_spans import (
    AmbiguousFindError,
    align_words_to_text,
    find_unique_char_span,
    iter_segment_word_spans,
    span_from_word_range,
)


def test_align_words_happy_path():
    text = "hello world today"
    words = [
        {"word": "hello", "start": 0.0, "end": 0.4},
        {"word": "world", "start": 0.5, "end": 0.9},
        {"word": "today", "start": 1.0, "end": 1.4},
    ]
    spans, ok = align_words_to_text(text, words)
    assert ok
    assert len(spans) == 3
    assert spans[1].text == "world"
    assert text[spans[1].char_start : spans[1].char_end] == "world"


def test_span_from_word_range_multiword():
    seg = {
        "text": "alpha beta gamma",
        "words": [
            {"word": "alpha", "start": 0.0, "end": 0.2},
            {"word": "beta", "start": 0.3, "end": 0.5},
            {"word": "gamma", "start": 0.6, "end": 0.8},
        ],
    }
    start, end, wrong = span_from_word_range(seg, 0, 1)
    assert wrong == "alpha beta"
    assert seg["text"][start:end] == "alpha beta"


def test_ambiguous_find_rejects_multiple():
    with pytest.raises(AmbiguousFindError) as ei:
        find_unique_char_span("foo bar foo", "foo")
    assert ei.value.match_count == 2


def test_unique_find_ok():
    assert find_unique_char_span("foo bar baz", "bar") == (4, 7)


def test_alignment_fail_falls_back_whitespace():
    text = "hello world"
    words = [{"word": "goodbye", "start": 0.0, "end": 0.1}]
    spans, ok = align_words_to_text(text, words)
    assert ok is False
    assert [s.text for s in spans] == ["hello", "world"]


def test_iter_segment_no_words_uses_whitespace():
    spans, aligned = iter_segment_word_spans({"text": "one two"})
    assert aligned is False
    assert [s.text for s in spans] == ["one", "two"]
