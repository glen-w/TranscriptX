"""Tests for affective label helpers."""

from __future__ import annotations

from types import SimpleNamespace

from transcriptx.core.analysis import emotion as emotion_module


def test_extract_nrc_emotion_scores_prefers_raw_emotion_scores() -> None:
    emo = SimpleNamespace(raw_emotion_scores={"joy": 2, "anger": 1, "x": "bad"})
    scores = emotion_module._extract_nrc_emotion_scores(emo)
    assert scores == {"joy": 2.0, "anger": 1.0}


def test_extract_nrc_emotion_scores_normalizes_affect_frequencies_aliases() -> None:
    emo = SimpleNamespace(affect_frequencies={"anticip": 0.4, "fear": 0.2, "meta": "x"})
    scores = emotion_module._extract_nrc_emotion_scores(emo)
    assert scores["anticipation"] == 0.4
    assert scores["fear"] == 0.2
    assert "meta" not in scores


def test_parse_pipeline_emotion_result_top1_keeps_primary_only() -> None:
    obj = emotion_module.EmotionAnalysis.__new__(emotion_module.EmotionAnalysis)
    obj.emotion_output_mode = "top1"
    obj.emotion_score_threshold = 0.5
    primary, scores = obj._parse_pipeline_emotion_result(
        [{"label": "joy", "score": 0.7}, {"label": "sadness", "score": 0.2}]
    )
    assert primary == "joy"
    assert scores == {"joy": 0.7}


def test_parse_pipeline_emotion_result_multilabel_applies_threshold() -> None:
    obj = emotion_module.EmotionAnalysis.__new__(emotion_module.EmotionAnalysis)
    obj.emotion_output_mode = "multilabel"
    obj.emotion_score_threshold = 0.3
    primary, scores = obj._parse_pipeline_emotion_result(
        [{"label": "joy", "score": 0.7}, {"label": "sadness", "score": 0.2}]
    )
    assert primary == "joy"
    assert scores == {"joy": 0.7}
