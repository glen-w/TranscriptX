"""Offline unit tests for acts ML classifier helpers (mocked sklearn)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.acts import ml_classifier as ml


@pytest.mark.unit
def test_initialize_transformer_disabled() -> None:
    clf = ml.MLDialogueActClassifier.__new__(ml.MLDialogueActClassifier)
    assert clf._initialize_transformer_model() is False


@pytest.mark.unit
def test_classify_heuristics_act_types() -> None:
    with patch.object(ml, "SKLEARN_AVAILABLE", False):
        clf = ml.MLDialogueActClassifier(use_context=True)
    samples = {
        "How are you?": "question",
        "yes I agree absolutely": "agreement",
        "no but however": "disagreement",
        "let's try how about we": "suggestion",
        "thanks thank you appreciate": "gratitude",
        "sorry apologize excuse me": "apology",
        "hello hi greetings": "greeting",
        "goodbye see you bye": "farewell",
        "um uh er ah hmm": "hesitation",
        "wait stop hold on": "interruption",
        "really amazing stuff": "emphasis",
        "maybe might could": "uncertainty",
        "plain remark about climate": "statement",
    }
    for text, expected in samples.items():
        result = clf._classify_with_heuristics(text)
        assert result.act_type == expected
        assert result.method == "heuristics"
        assert result.confidence > 0


@pytest.mark.unit
def test_prepare_input_with_context() -> None:
    with patch.object(ml, "SKLEARN_AVAILABLE", False):
        clf = ml.MLDialogueActClassifier(use_context=True)
    assert clf._prepare_input_with_context("hi", None) == "hi"
    assert clf._prepare_input_with_context("hi", {}) == "hi"
    out = clf._prepare_input_with_context(
        "now",
        {"previous_utterances": ["one", "two", "three", "four"]},
    )
    assert "[SEP]" in out
    assert out.endswith("now")
    assert "one" not in out  # window=3 keeps last three


@pytest.mark.unit
def test_traditional_ml_untrained_falls_back_to_heuristics() -> None:
    with patch.object(ml, "SKLEARN_AVAILABLE", False):
        clf = ml.MLDialogueActClassifier(use_context=False)
    clf.tfidf_vectorizer = MagicMock()
    clf.random_forest = MagicMock(spec=[])  # no estimators_
    result = clf._classify_with_traditional_ml("Is this a question?")
    assert result is not None
    assert result.method == "heuristics"
    assert result.act_type == "question"


@pytest.mark.unit
def test_traditional_ml_trained_path_classifies() -> None:
    with patch.object(ml, "SKLEARN_AVAILABLE", False):
        clf = ml.MLDialogueActClassifier(use_context=False)
    clf.tfidf_vectorizer = MagicMock()
    clf.random_forest = MagicMock()
    clf.random_forest.estimators_ = [object(), object()]
    question = clf._classify_with_traditional_ml("What time is it?")
    assert question.method == "traditional_ml"
    assert question.act_type == "question"
    agree = clf._classify_with_traditional_ml("yes I agree you are correct")
    assert agree.act_type == "agreement"
    disagree = clf._classify_with_traditional_ml("no but however")
    assert disagree.act_type == "disagreement"
    stmt = clf._classify_with_traditional_ml("the sky is blue")
    assert stmt.act_type == "statement"


@pytest.mark.unit
def test_traditional_ml_missing_models_returns_none() -> None:
    with patch.object(ml, "SKLEARN_AVAILABLE", False):
        clf = ml.MLDialogueActClassifier(use_context=False)
    clf.tfidf_vectorizer = None
    clf.random_forest = None
    assert clf._classify_with_traditional_ml("x") is None


@pytest.mark.unit
def test_traditional_ml_exception_returns_none() -> None:
    with patch.object(ml, "SKLEARN_AVAILABLE", False):
        clf = ml.MLDialogueActClassifier(use_context=False)
    clf.tfidf_vectorizer = MagicMock()

    class Boom:
        @property
        def estimators_(self):
            raise RuntimeError("unexpected")

    clf.random_forest = Boom()
    assert clf._classify_with_traditional_ml("hello") is None


@pytest.mark.unit
def test_classify_with_rules_and_fallback() -> None:
    with patch.object(ml, "SKLEARN_AVAILABLE", False):
        clf = ml.MLDialogueActClassifier(use_context=True)
    with patch.object(
        ml,
        "rules_classify_utterance",
        return_value={
            "act_type": "question",
            "confidence": 0.9,
            "probabilities": {"question": 0.9},
        },
    ):
        result = clf._classify_with_rules("huh?", None)
    assert result.method == "rules"
    assert result.fallback_used is True
    assert result.act_type == "question"

    with patch.object(
        ml, "rules_classify_utterance", side_effect=RuntimeError("broken")
    ):
        fallback = clf._classify_with_rules("x", None)
    assert fallback.method == "fallback"
    assert fallback.act_type == "statement"


@pytest.mark.unit
def test_classify_with_ml_uses_rules_when_no_vectorizer() -> None:
    with patch.object(ml, "SKLEARN_AVAILABLE", False):
        clf = ml.MLDialogueActClassifier(use_context=False)
    with patch.object(
        clf,
        "_classify_with_rules",
        return_value=ml.MLClassificationResult(
            act_type="statement",
            confidence=0.5,
            method="rules",
            probabilities={},
            context_used=False,
            fallback_used=True,
        ),
    ) as rules:
        out = clf.classify("hello world")
    assert out.act_type == "statement"
    rules.assert_called_once()


@pytest.mark.unit
def test_initialize_traditional_ml_success_and_failure() -> None:
    with patch.object(ml, "SKLEARN_AVAILABLE", True):
        clf = ml.MLDialogueActClassifier.__new__(ml.MLDialogueActClassifier)
        clf.tfidf_vectorizer = None
        clf.random_forest = None
        cfg = SimpleNamespace(
            analysis=SimpleNamespace(
                vectorization=SimpleNamespace(max_features=100, ngram_range=(1, 2))
            )
        )
        with (
            patch("transcriptx.core.utils.config.get_config", return_value=cfg),
            patch.object(ml, "TfidfVectorizer", MagicMock()),
            patch.object(ml, "RandomForestClassifier", MagicMock()),
        ):
            assert clf._initialize_traditional_ml() is True
            assert clf.tfidf_vectorizer is not None

        with patch(
            "transcriptx.core.utils.config.get_config",
            side_effect=RuntimeError("cfg boom"),
        ):
            assert clf._initialize_traditional_ml() is False


@pytest.mark.unit
def test_create_ml_classifier_and_classify_utterance() -> None:
    fake = MagicMock()
    fake.ml_available = True
    fake.classify_with_ml.return_value = SimpleNamespace(act_type="question")
    with patch.object(ml, "MLDialogueActClassifier", return_value=fake):
        created = ml.create_ml_classifier("bert-base-uncased", use_context=True)
    assert created is fake

    with patch.object(ml, "create_ml_classifier", return_value=fake):
        assert ml.classify_utterance_ml("Why?") == "question"

    with patch.object(ml, "create_ml_classifier", side_effect=RuntimeError("nope")):
        assert ml.classify_utterance_ml("Why?") == "statement"


@pytest.mark.unit
def test_create_ml_classifier_fallback_instance_on_init_error() -> None:
    with patch.object(
        ml.MLDialogueActClassifier,
        "__init__",
        side_effect=RuntimeError("init fail"),
    ):
        clf = ml.create_ml_classifier("bert-base-uncased", True)
    assert clf.ml_available is False
    assert clf.tfidf_vectorizer is None
    assert clf.model_name == "bert-base-uncased"


@pytest.mark.unit
def test_get_act_types_returns_list() -> None:
    with patch.object(ml, "SKLEARN_AVAILABLE", False):
        clf = ml.MLDialogueActClassifier(use_context=False)
    types = clf._get_act_types()
    assert isinstance(types, list)
    assert len(types) > 0
