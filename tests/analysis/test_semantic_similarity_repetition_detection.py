"""Unit tests for semantic similarity repetition detection helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.core.analysis.semantic_similarity.repetition_detection import (
    classify_agreement_disagreement_advanced,
    classify_agreement_disagreement_basic,
    detect_cross_speaker_repetitions_advanced,
    detect_cross_speaker_repetitions_basic,
    detect_speaker_repetitions_advanced,
    detect_speaker_repetitions_basic,
)


def _seg(speaker: str, text: str, start: float, end: float | None = None) -> dict:
    return {
        "speaker": speaker,
        "text": text,
        "start": start,
        "end": end if end is not None else start + 1.0,
    }


def _state(max_comparisons: int = 10_000) -> SimpleNamespace:
    return SimpleNamespace(comparison_count=0, max_comparisons=max_comparisons)


@pytest.mark.unit
def test_classify_agreement_disagreement_advanced_paths() -> None:
    assert (
        classify_agreement_disagreement_advanced(
            "I agree completely", "yes exactly", 0.5, "TEST"
        )
        == "agreement"
    )
    assert (
        classify_agreement_disagreement_advanced(
            "I disagree", "that is wrong", 0.5, "TEST"
        )
        == "disagreement"
    )
    assert (
        classify_agreement_disagreement_advanced(
            "plain text", "other text", 0.5, "TEST"
        )
        == "neutral"
    )


@pytest.mark.unit
def test_classify_agreement_disagreement_basic_paths() -> None:
    assert (
        classify_agreement_disagreement_basic("I agree with you", "good point", 0.5)
        == "agreement"
    )
    assert (
        classify_agreement_disagreement_basic("I disagree", "but however", 0.5)
        == "disagreement"
    )
    assert (
        classify_agreement_disagreement_basic("neutral wording", "also neutral", 0.9)
        == "paraphrase"
    )
    assert (
        classify_agreement_disagreement_basic("neutral wording", "also neutral", 0.5)
        == "neutral"
    )


@pytest.mark.unit
def test_detect_speaker_repetitions_advanced_hits_and_near_skip() -> None:
    state = _state()
    # Pair 0↔1 is far enough (>=30s); 0↔2 and 1↔2 are near (<30) so skipped.
    segs = [
        _seg("Alice", "We should ship the feature next week together.", 0),
        _seg("Alice", "We should ship the feature next week together.", 60),
        _seg("Alice", "Near duplicate that should be skipped for time.", 5),
    ]
    reps = detect_speaker_repetitions_advanced(
        "Alice",
        segs,
        similarity_fn=lambda a, b: 0.95 if "ship" in a and "ship" in b else 0.2,
        comparison_state=state,
        log_tag="TEST",
    )
    assert len(reps) == 1
    assert reps[0]["type"] == "self_repetition"
    assert reps[0]["similarity"] == 0.95


@pytest.mark.unit
def test_detect_speaker_repetitions_advanced_respects_comparison_limit() -> None:
    # comparison_count starts above max → loop breaks immediately.
    state = SimpleNamespace(comparison_count=5, max_comparisons=0)
    segs = [
        _seg("Alice", "Meaningful content about shipping features soon.", 0),
        _seg("Alice", "Meaningful content about shipping features soon.", 60),
    ]
    reps = detect_speaker_repetitions_advanced(
        "Alice",
        segs,
        similarity_fn=lambda a, b: 0.99,
        comparison_state=state,
        log_tag="TEST",
    )
    assert reps == []


@pytest.mark.unit
def test_detect_cross_speaker_repetitions_advanced() -> None:
    state = _state()
    segs = [
        _seg("Alice", "I completely agree with that shipping plan.", 0),
        _seg("Bob", "I completely agree with that shipping plan.", 20),
        _seg("Alice", "Too close in time for cross detection path.", 2),
    ]
    reps = detect_cross_speaker_repetitions_advanced(
        segs,
        similarity_fn=lambda a, b: 0.85,
        comparison_state=state,
        log_tag="TEST",
    )
    assert len(reps) >= 1
    assert reps[0]["type"] == "cross_speaker_repetition"
    assert reps[0].get("classification") == "agreement"


@pytest.mark.unit
def test_detect_speaker_repetitions_basic_window_and_threshold() -> None:
    state = _state()
    segs = [
        _seg("Alice", "We need a longer sentence for filtering words.", 0),
        _seg("Alice", "We need a longer sentence for filtering words.", 30),
        _seg("Alice", "Far outside the window and should not match again.", 500),
    ]

    def filter_fn(items, max_n):
        return items[:max_n]

    reps = detect_speaker_repetitions_basic(
        "Alice",
        segs,
        similarity_fn=lambda a, b: 0.9,
        comparison_state=state,
        similarity_threshold=0.6,
        time_window=60,
        max_segments_per_speaker=100,
        filter_segments_fn=filter_fn,
        log_tag="TEST",
    )
    assert len(reps) == 1
    assert reps[0]["type"] == "self_repetition"


@pytest.mark.unit
def test_detect_speaker_repetitions_basic_uses_filter_when_over_cap() -> None:
    state = _state()
    segs = [
        _seg("Alice", f"Long enough meaningful sentence number {i} here.", float(i * 5))
        for i in range(6)
    ]
    seen = {"called": False}

    def filter_fn(items, max_n):
        seen["called"] = True
        return items[:max_n]

    detect_speaker_repetitions_basic(
        "Alice",
        segs,
        similarity_fn=lambda a, b: 0.1,
        comparison_state=state,
        similarity_threshold=0.9,
        time_window=600,
        max_segments_per_speaker=3,
        filter_segments_fn=filter_fn,
        log_tag="TEST",
    )
    assert seen["called"] is True


@pytest.mark.unit
def test_detect_cross_speaker_repetitions_basic() -> None:
    state = _state()
    segs = [
        _seg("Alice", "I completely agree with that plan today.", 0),
        _seg("Bob", "I completely agree with that plan today.", 20),
        _seg("Bob", "hi", 40),  # too few words
    ]
    reps = detect_cross_speaker_repetitions_basic(
        segs,
        similarity_fn=lambda a, b: 0.9,
        comparison_state=state,
        similarity_threshold=0.6,
        time_window=600,
        max_segments_for_cross_speaker=100,
        log_tag="TEST",
    )
    assert len(reps) == 1
    assert reps[0]["type"] == "cross_speaker"
    assert reps[0]["agreement_type"] == "agreement"
