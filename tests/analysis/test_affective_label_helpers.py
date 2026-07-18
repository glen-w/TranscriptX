"""Tests for affective / lexical label helpers."""

from __future__ import annotations

from transcriptx.core.analysis.emotion.lexical_pipeline import (
    PLUTCHIK_EIGHT,
    build_lexicon_from_nrclex,
    normalize_profile,
    score_segment_text,
)


def test_build_lexicon_normalizes_anticip_alias() -> None:
    class _Fake:
        AffectDict = {"x": ["anticip", "fear", "meta"]}

        def __init__(self, text: str = "") -> None:
            self.lexicon = self.AffectDict

    lexicon = build_lexicon_from_nrclex(_Fake)
    assert lexicon["x"] == ["anticipation", "fear", "meta"]


def test_normalize_profile_keeps_plutchik_keys() -> None:
    scores = normalize_profile({"joy": 2, "anger": 1}, PLUTCHIK_EIGHT)
    assert set(scores) == set(PLUTCHIK_EIGHT)
    assert abs(scores["joy"] - 2 / 3) < 1e-9
    assert scores["sadness"] == 0.0


def test_score_segment_text_applies_lexicon_hits() -> None:
    lexicon = {"happy": ["joy", "positive"], "sad": ["sadness", "negative"]}
    result = score_segment_text("happy sad", lexicon)
    assert result.evaluation_state == "scored"
    assert result.assignment_counts["joy"] == 1
    assert result.assignment_counts["sadness"] == 1
    assert result.valence_assignment_counts["positive"] == 1


def test_score_segment_text_empty_is_zero_safe() -> None:
    result = score_segment_text("   ", {})
    assert result.evaluation_state == "empty"
    assert result.coverage == 0.0
    assert all(v == 0.0 for v in result.emotion_scores.values())
