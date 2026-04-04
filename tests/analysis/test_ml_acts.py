"""
Tests for ML-based dialogue act classification module.

This module tests ML-based dialogue act classification.
"""

from unittest.mock import patch
import pytest

from transcriptx.core.analysis.acts.ml_classifier import (
    MLDialogueActClassifier,
    MLClassificationResult,
)


class TestMLDialogueActClassifier:
    """Tests for MLDialogueActClassifier."""

    @pytest.fixture
    def classifier(self):
        """Fixture for MLDialogueActClassifier instance."""
        return MLDialogueActClassifier(use_context=False)

    def test_classifier_initialization(self):
        """Test classifier initialization."""
        classifier = MLDialogueActClassifier()

        assert classifier is not None
        assert hasattr(classifier, "classify")

    @patch("transcriptx.core.analysis.acts.ml_classifier.TRANSFORMERS_AVAILABLE", False)
    @patch("transcriptx.core.analysis.acts.ml_classifier.rules_classify_utterance")
    def test_classifier_fallback_to_rules(self, mock_rules, classifier):
        """Test that classifier falls back to rules when ML unavailable."""
        mock_rules.return_value = "statement"

        result = classifier.classify("This is a test statement.")

        assert result is not None
        # Should use fallback
        mock_rules.assert_called()

    @patch("transcriptx.core.analysis.acts.ml_classifier.TRANSFORMERS_AVAILABLE", True)
    def test_classifier_with_transformers(self, classifier):
        """
        Transformers availability should not break classification.

        Note: transformer-based dialogue-act classification is intentionally disabled in
        `MLDialogueActClassifier._initialize_transformer_model()` (untrained base models).
        """
        result = classifier.classify("This is a test statement.")
        assert result is not None
        assert result.method in {"traditional_ml", "heuristics", "rules", "fallback"}

    def test_classifier_empty_text(self, classifier):
        """Test classifier with empty text."""
        result = classifier.classify("")

        # Should handle gracefully
        assert result is not None

    @patch("transcriptx.core.analysis.acts.ml_classifier.rules_classify_utterance")
    def test_classifier_question_detection(self, mock_rules, classifier):
        """Test question detection."""
        mock_rules.return_value = "question"

        result = classifier.classify("What is this?")

        assert result is not None

    @patch("transcriptx.core.analysis.acts.ml_classifier.rules_classify_utterance")
    def test_classifier_statement_detection(self, mock_rules, classifier):
        """Test statement detection."""
        mock_rules.return_value = "statement"

        result = classifier.classify("This is a statement.")

        assert result is not None


class TestMLClassificationResult:
    """Tests for MLClassificationResult dataclass."""

    def test_result_creation(self):
        """Test creating MLClassificationResult."""
        result = MLClassificationResult(
            act_type="statement",
            confidence=0.9,
            method="transformer",
            probabilities={"statement": 0.9, "question": 0.1},
            context_used=False,
        )

        assert result.act_type == "statement"
        assert result.confidence == 0.9
        assert result.method == "transformer"
        assert not result.context_used
