"""Unit tests for TranscriptSimplifier and related helpers."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.simplified_transcript.simplify import (
    SimplifierConfig,
    TranscriptSimplifier,
    _collapse_whitespace_and_punct,
    _normalize_for_match,
)


@pytest.mark.unit
def test_normalize_for_match_lowercases_and_strips_punct() -> None:
    assert _normalize_for_match("  Hello, WORLD!! ") == "hello world"
    assert _normalize_for_match("A...B") == "a b"
    assert _normalize_for_match("") == ""


@pytest.mark.unit
def test_collapse_whitespace_and_punct() -> None:
    # Trailing punctuation is stripped by the helper.
    assert _collapse_whitespace_and_punct("  hello   ,  world..  ") == "hello, world"
    assert _collapse_whitespace_and_punct(",,leading") == "leading"
    assert _collapse_whitespace_and_punct("trailing!!") == "trailing"


@pytest.mark.unit
def test_clean_utterance_removes_tics() -> None:
    simplifier = TranscriptSimplifier(tics_list=["um", "you know"])
    assert simplifier.clean_utterance("Um, I think, you know, we should go.") == (
        "I think, we should go"
    )
    assert simplifier.clean_utterance("") == ""


@pytest.mark.unit
def test_is_agreement_phrases_and_default_acks() -> None:
    simplifier = TranscriptSimplifier(agreements_list=["I agree", "absolutely"])
    assert simplifier.is_agreement("I agree!") is True
    assert simplifier.is_agreement("Absolutely.") is True
    assert simplifier.is_agreement("yeah") is True  # default ack
    assert simplifier.is_agreement("lets discuss the budget") is False
    assert simplifier.is_agreement("") is False


@pytest.mark.unit
def test_is_agreement_skips_default_acks_when_drop_disabled() -> None:
    simplifier = TranscriptSimplifier(
        agreements_list=[],
        config=SimplifierConfig(drop_agreements=False),
    )
    assert simplifier.is_agreement("yeah") is False


@pytest.mark.unit
def test_simplify_drops_tics_agreements_and_consecutive_duplicates() -> None:
    simplifier = TranscriptSimplifier(
        tics_list=["um", "uh"],
        agreements_list=["yeah"],
        config=SimplifierConfig(
            drop_agreements=True,
            drop_duplicates=True,
            duplicates_consecutive_only=True,
        ),
    )
    transcript = [
        {"speaker": "Alice", "text": "Um, we should start now."},
        {"speaker": "Bob", "text": "Yeah"},
        {"speaker": "Alice", "text": "We should start now."},
        {"speaker": "Alice", "text": "We should start now."},  # consecutive dup
        {"speaker": "Bob", "text": "Ok, next topic."},
    ]
    out = simplifier.simplify(transcript)
    texts = [t["text"] for t in out]
    assert texts == ["we should start now", "Ok, next topic"]
    # Cleaned first turn drops leading tic; consecutive Alice dup removed
    assert all(t["speaker"] in {"Alice", "Bob"} for t in out)


@pytest.mark.unit
def test_simplify_global_duplicates_when_consecutive_only_false() -> None:
    simplifier = TranscriptSimplifier(
        config=SimplifierConfig(
            drop_duplicates=True,
            duplicates_consecutive_only=False,
            duplicates_per_speaker=True,
        ),
    )
    transcript = [
        {"speaker": "Alice", "text": "Same idea here."},
        {"speaker": "Bob", "text": "Different."},
        {"speaker": "Alice", "text": "Same idea here."},  # non-consecutive dup
    ]
    out = simplifier.simplify(transcript)
    assert [t["text"] for t in out] == ["Same idea here", "Different"]


@pytest.mark.unit
def test_simplify_merge_consecutive_same_speaker() -> None:
    simplifier = TranscriptSimplifier(
        config=SimplifierConfig(
            drop_duplicates=False,
            merge_consecutive_same_speaker=True,
        ),
    )
    transcript = [
        {"speaker": "Alice", "text": "First point."},
        {"speaker": "Alice", "text": "Second point."},
        {"speaker": "Bob", "text": "Reply."},
    ]
    out = simplifier.simplify(transcript)
    assert len(out) == 2
    assert out[0]["speaker"] == "Alice"
    assert "First point" in out[0]["text"]
    assert "Second point" in out[0]["text"]
    assert out[1] == {"speaker": "Bob", "text": "Reply"}


@pytest.mark.unit
def test_simplify_min_word_count_and_empty_text() -> None:
    simplifier = TranscriptSimplifier(
        config=SimplifierConfig(min_word_count=3, drop_agreements=False),
    )
    transcript = [
        {"speaker": "Alice", "text": ""},
        {"speaker": "Alice", "text": "   "},
        {"speaker": "Bob", "text": "Too short"},
        {"speaker": "Bob", "text": "This has enough words."},
    ]
    out = simplifier.simplify(transcript)
    assert len(out) == 1
    assert out[0]["speaker"] == "Bob"
    assert "enough" in out[0]["text"]
