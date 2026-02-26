"""
Unit tests for affect_tension metrics, sentiment normalization, and emotion parsing.

No live Hugging Face calls; uses fixtures and mocks.
"""

import pytest

from transcriptx.core.analysis.affect_tension.metrics import (
    emotion_entropy,
    trust_like_score,
    affect_mismatch_posneg,
    affect_trust_neutral,
    emotion_volatility_proxy,
)
from transcriptx.core.analysis.sentiment import _normalize_transformers_sentiment
from transcriptx.core.viz.specs import (
    BarCategoricalSpec,
    HeatmapMatrixSpec,
    LineTimeSeriesSpec,
)


class TestEmotionEntropy:
    """Tests for emotion_entropy."""

    def test_empty_scores_returns_none(self):
        assert emotion_entropy({}) is None

    def test_single_label_zero_entropy(self):
        assert emotion_entropy({"joy": 1.0}) == 0.0

    def test_uniform_two_labels(self):
        # -0.5*log2(0.5) * 2 = 1.0
        ent = emotion_entropy({"joy": 0.5, "sadness": 0.5})
        assert ent is not None
        assert abs(ent - 1.0) < 1e-6

    def test_skips_zero_probs(self):
        ent = emotion_entropy({"joy": 1.0, "sadness": 0.0})
        assert ent is not None
        assert ent == 0.0

    def test_raw_scores_normalized_internally(self):
        ent = emotion_entropy({"a": 1.0, "b": 1.0, "c": 2.0})
        assert ent is not None
        assert ent > 0


class TestMismatchRuleLogic:
    """Tests for affect_mismatch_posneg and affect_trust_neutral."""

    def test_posneg_mismatch_positive_emotion_negative_sentiment(self):
        assert (
            affect_mismatch_posneg(
                sentiment_compound_norm=-0.5,
                emotion_scores={"joy": 0.8},
                pos_emotion_threshold=0.3,
                mismatch_compound_threshold=-0.1,
            )
            is True
        )

    def test_posneg_no_mismatch_positive_sentiment(self):
        assert (
            affect_mismatch_posneg(
                sentiment_compound_norm=0.5,
                emotion_scores={"joy": 0.8},
                pos_emotion_threshold=0.3,
                mismatch_compound_threshold=-0.1,
            )
            is False
        )

    def test_posneg_no_mismatch_negative_emotion(self):
        assert (
            affect_mismatch_posneg(
                sentiment_compound_norm=-0.5,
                emotion_scores={"anger": 0.8},
                pos_emotion_threshold=0.3,
                mismatch_compound_threshold=-0.1,
            )
            is False
        )

    def test_trust_neutral_none_when_no_trust_like(self):
        assert (
            affect_trust_neutral(
                sentiment_compound_norm=0.0,
                trust_like=None,
                trust_like_threshold=0.3,
            )
            is None
        )

    def test_trust_neutral_true_when_neutral_sentiment_high_trust(self):
        assert (
            affect_trust_neutral(
                sentiment_compound_norm=0.0,
                trust_like=0.5,
                trust_like_threshold=0.3,
            )
            is True
        )

    def test_trust_neutral_false_when_negative_sentiment(self):
        assert (
            affect_trust_neutral(
                sentiment_compound_norm=-0.5,
                trust_like=0.5,
                trust_like_threshold=0.3,
            )
            is False
        )


class TestTransformersSentimentNormalization:
    """Tests for _normalize_transformers_sentiment to compound_norm."""

    def test_empty_result(self):
        out = _normalize_transformers_sentiment([])
        assert out["compound"] == 0.0
        assert 0 <= out["pos"] <= 1
        assert 0 <= out["neg"] <= 1
        assert 0 <= out["neu"] <= 1

    def test_positive_dominant(self):
        result = [
            {"label": "positive", "score": 0.9},
            {"label": "negative", "score": 0.05},
            {"label": "neutral", "score": 0.05},
        ]
        out = _normalize_transformers_sentiment(result)
        assert out["compound"] > 0
        assert out["pos"] > out["neg"]
        assert out["label"] == "positive"

    def test_negative_dominant(self):
        result = [
            {"label": "positive", "score": 0.05},
            {"label": "negative", "score": 0.9},
            {"label": "neutral", "score": 0.05},
        ]
        out = _normalize_transformers_sentiment(result)
        assert out["compound"] < 0
        assert out["neg"] > out["pos"]
        assert out["label"] == "negative"

    def test_compound_in_range(self):
        result = [
            {"label": "positive", "score": 0.5},
            {"label": "negative", "score": 0.3},
            {"label": "neutral", "score": 0.2},
        ]
        out = _normalize_transformers_sentiment(result)
        assert -1 <= out["compound"] <= 1
        assert abs(out["pos"] + out["neg"] + out["neu"] - 1.0) < 1e-6


class TestEmotionParsingSingleLabel:
    """Tests for parsing single-label pipeline output into context_emotion_scores."""

    @pytest.fixture
    def emotion_module(self):
        from unittest.mock import MagicMock, patch
        from transcriptx.core.analysis.emotion import EmotionAnalysis

        cfg = MagicMock()
        cfg.analysis.emotion_model_name = "test/model"
        cfg.analysis.emotion_output_mode = "top1"
        cfg.analysis.emotion_score_threshold = 0.30
        with patch("transcriptx.core.utils.config.get_config", return_value=cfg):
            with patch(
                "transcriptx.core.analysis.emotion._load_nrclex", return_value=None
            ):
                with patch(
                    "transcriptx.core.analysis.emotion._load_emotion_model",
                    return_value=None,
                ):
                    module = EmotionAnalysis()
        return module

    def test_single_label_primary_and_scores(self, emotion_module):
        emotion_module.emotion_output_mode = "top1"
        emotion_module.emotion_score_threshold = 0.30
        result = [{"label": "joy", "score": 0.95}]
        primary, scores = emotion_module._parse_pipeline_emotion_result(result)
        assert primary == "joy"
        assert scores == {"joy": 0.95}

    def test_single_label_top1_keeps_only_primary(self, emotion_module):
        emotion_module.emotion_output_mode = "top1"
        emotion_module.emotion_score_threshold = 0.30
        result = [
            {"label": "joy", "score": 0.6},
            {"label": "sadness", "score": 0.3},
            {"label": "anger", "score": 0.1},
        ]
        primary, scores = emotion_module._parse_pipeline_emotion_result(result)
        assert primary == "joy"
        assert scores == {"joy": 0.6}


class TestEmotionParsingMultilabel:
    """Tests for parsing multilabel pipeline output into context_emotion_scores."""

    @pytest.fixture
    def emotion_module(self):
        from unittest.mock import MagicMock, patch
        from transcriptx.core.analysis.emotion import EmotionAnalysis

        cfg = MagicMock()
        cfg.analysis.emotion_model_name = "test/model"
        cfg.analysis.emotion_output_mode = "multilabel"
        cfg.analysis.emotion_score_threshold = 0.30
        with patch("transcriptx.core.utils.config.get_config", return_value=cfg):
            with patch(
                "transcriptx.core.analysis.emotion._load_nrclex", return_value=None
            ):
                with patch(
                    "transcriptx.core.analysis.emotion._load_emotion_model",
                    return_value=None,
                ):
                    module = EmotionAnalysis()
        return module

    def test_multilabel_above_threshold(self, emotion_module):
        emotion_module.emotion_output_mode = "multilabel"
        emotion_module.emotion_score_threshold = 0.30
        result = [
            {"label": "joy", "score": 0.7},
            {"label": "gratitude", "score": 0.5},
            {"label": "sadness", "score": 0.2},
        ]
        primary, scores = emotion_module._parse_pipeline_emotion_result(result)
        assert primary == "joy"
        assert "joy" in scores and scores["joy"] == 0.7
        assert "gratitude" in scores and scores["gratitude"] == 0.5
        assert "sadness" not in scores  # below 0.30

    def test_multilabel_primary_still_max(self, emotion_module):
        emotion_module.emotion_output_mode = "multilabel"
        emotion_module.emotion_score_threshold = 0.25
        result = [
            {"label": "approval", "score": 0.4},
            {"label": "joy", "score": 0.6},
        ]
        primary, scores = emotion_module._parse_pipeline_emotion_result(result)
        assert primary == "joy"
        assert set(scores.keys()) == {"approval", "joy"}


class TestEmotionVolatilityProxy:
    """Tests for emotion_volatility_proxy."""

    def test_first_segment_zero(self):
        assert emotion_volatility_proxy(0, ["joy", "sadness"], 3) == 0.0

    def test_no_change_zero_volatility(self):
        labels = ["joy", "joy", "joy", "joy"]
        assert emotion_volatility_proxy(3, labels, 3) == 0.0

    def test_all_different_volatility_one(self):
        labels = ["joy", "sadness", "anger", "joy"]
        vol = emotion_volatility_proxy(3, labels, 3)
        # At index 3 current="joy"; preceding 3 are joy, sadness, anger -> 2/3 different
        assert abs(vol - 2.0 / 3.0) < 1e-6

    def test_empty_labels(self):
        assert emotion_volatility_proxy(1, [], 3) == 0.0


class TestTrustLikeScore:
    """Tests for trust_like_score."""

    def test_trust_direct(self):
        assert trust_like_score({"trust": 0.8}) == 0.8

    def test_trust_like_weighted(self):
        s = trust_like_score({"approval": 0.5, "gratitude": 0.5})
        assert s is not None
        assert 0 <= s <= 1

    def test_empty_none(self):
        assert trust_like_score({}) is None


def test_affect_tension_emits_chart_specs() -> None:
    from transcriptx.core.analysis.affect_tension import AffectTensionAnalysis

    segments = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Thanks, I really appreciate it.",
            "start_s": 0.0,
            "context_emotion_scores": {"joy": 0.7},
            "context_emotion_primary": "joy",
            "sentiment_compound_norm": -0.2,
            "affect_mismatch_posneg": True,
            "affect_trust_neutral": False,
            "emotion_entropy": 1.2,
            "emotion_volatility_proxy": 0.1,
            "mismatch_type": "posneg_mismatch",
        },
        {
            "speaker": "Bob",
            "speaker_db_id": 2,
            "text": "Okay.",
            "start_s": 1.5,
            "context_emotion_scores": {"neutral": 0.8},
            "context_emotion_primary": "neutral",
            "sentiment_compound_norm": 0.0,
            "affect_mismatch_posneg": False,
            "affect_trust_neutral": True,
            "emotion_entropy": 0.2,
            "emotion_volatility_proxy": 0.0,
            "mismatch_type": "trust_neutral",
        },
    ]
    derived_indices = {
        "global": {
            "polite_tension_index": 0.4,
            "suppressed_conflict_score": 0.2,
            "institutional_tone_affect_delta": 0.1,
        },
        "by_speaker": {
            "Alice": {
                "polite_tension_index": 0.5,
                "suppressed_conflict_score": 0.3,
                "institutional_tone_affect_delta": 0.2,
            },
            "Bob": {
                "polite_tension_index": 0.2,
                "suppressed_conflict_score": 0.1,
                "institutional_tone_affect_delta": 0.05,
            },
        },
    }
    results = {
        "segments": segments,
        "derived_indices": derived_indices,
        "metadata": {},
    }

    class DummyOutputService:
        base_name = "fixture"

        def __init__(self) -> None:
            self.charts: list[object] = []

        def save_data(self, *args, **kwargs) -> None:
            return None

        def save_chart(self, spec, *args, **kwargs) -> None:
            self.charts.append(spec)

    output_service = DummyOutputService()
    module = AffectTensionAnalysis()
    module._save_results(results, output_service)

    assert any(isinstance(spec, BarCategoricalSpec) for spec in output_service.charts)
    assert any(isinstance(spec, LineTimeSeriesSpec) for spec in output_service.charts)
    assert any(isinstance(spec, HeatmapMatrixSpec) for spec in output_service.charts)
