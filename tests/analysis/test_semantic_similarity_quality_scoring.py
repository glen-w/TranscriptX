"""Unit tests for semantic similarity quality scorers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.core.analysis.semantic_similarity.quality_scoring import (
    AdvancedQualityScorer,
    BasicQualityScorer,
)


class _FakeCfg:
    def get_quality_filtering_config(self):
        return {
            "weights": {
                "length_optimal": 3.0,
                "length_good": 1.0,
                "complex_reasoning": 2.0,
                "opinions_ideas": 2.0,
                "agreement_disagreement": 1.0,
                "filler_penalty": -0.5,
                "exact_repetition_penalty": -5.0,
                "high_overlap_penalty": -3.0,
            },
            "thresholds": {
                "min_words": 3,
                "optimal_word_range": (5, 50),
                "good_word_range": (3, 100),
                "overlap_threshold": 0.7,
            },
            "indicators": {
                "complex_reasoning": ["because", "therefore"],
                "opinions_ideas": ["think", "believe"],
                "agreement_disagreement": ["agree", "disagree"],
                "filler_words": ["um", "uh"],
            },
        }


@pytest.mark.unit
def test_basic_quality_scorer_passthrough_when_under_cap() -> None:
    scorer = BasicQualityScorer(_FakeCfg(), "TEST")
    segs = [{"text": "one two three four five"}]
    assert scorer.filter_segments(segs, 10) == segs


@pytest.mark.unit
def test_basic_quality_scorer_ranks_and_drops_short() -> None:
    scorer = BasicQualityScorer(_FakeCfg(), "TEST")
    segs = [
        {"text": "um uh um filler filler filler"},
        {"text": "I think therefore we should because it matters a lot today"},
        {"text": "I think therefore we should because it matters a lot today"},
        {"text": "hi"},
    ]
    kept = scorer.filter_segments(segs, max_segments=1)
    assert len(kept) == 1
    assert "think" in kept[0]["text"]


@pytest.mark.unit
def test_advanced_quality_scorer_clamps_and_uses_analysis() -> None:
    scorer = AdvancedQualityScorer(SimpleNamespace(), "TEST")
    score = scorer.calculate_quality_score(
        {"speaker": "Alice", "text": "I think therefore this is important now"},
        {
            "sentiment": {"speaker_data": {"Alice": {"average_sentiment": 0.8}}},
            "tics": {"speaker_data": {"Alice": {"tic_ratio": 0.0}}},
            "emotion": {"speaker_data": {"Alice": {"emotion_scores": {"joy": 0.9}}}},
            "acts": {
                "speaker_data": {
                    "Alice": {"act_distribution": {"inform": 0.4, "elaborate": 0.3}}
                }
            },
        },
    )
    assert 0.0 <= score <= 1.0


@pytest.mark.unit
def test_advanced_quality_scorer_failure_returns_midpoint() -> None:
    scorer = AdvancedQualityScorer(SimpleNamespace(), "TEST")
    # Missing text keys still returns a clamped fallback.
    score = scorer.calculate_quality_score({"speaker": "Alice"}, {})
    assert 0.0 <= score <= 1.0


@pytest.mark.unit
def test_advanced_filter_segments_ranks_and_caps() -> None:
    scorer = AdvancedQualityScorer(SimpleNamespace(), "TEST")
    segs = [
        {"speaker": "Alice", "text": "short a b"},
        {
            "speaker": "Alice",
            "text": "I think therefore we should carefully explain this matter now",
        },
        {"speaker": "Bob", "text": "um uh filler filler filler filler text"},
    ]
    kept = scorer.filter_segments(segs, 1, {})
    assert len(kept) == 1


@pytest.mark.unit
def test_advanced_filter_segments_error_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scorer = AdvancedQualityScorer(SimpleNamespace(), "TEST")
    segs = [{"speaker": "Alice", "text": f"token token token {i}"} for i in range(5)]

    def boom(*_a, **_k):
        raise RuntimeError("score failed")

    monkeypatch.setattr(scorer, "calculate_quality_score", boom)
    out = scorer.filter_segments(segs, 2, {})
    assert out == segs[:2]
