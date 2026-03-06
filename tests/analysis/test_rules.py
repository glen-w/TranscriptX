"""
Tests for rules-based analysis components.

This module tests rule-based dialogue act classification patterns.
"""

import re

from transcriptx.core.analysis.acts.rules import CUE_PHRASES


class TestRulesPatterns:
    """Tests for rule-based patterns."""

    def test_question_patterns(self):
        """Test question detection patterns."""
        question_patterns = CUE_PHRASES.get("question", [])

        assert len(question_patterns) > 0

        # Test direct question
        test_text = "What is this?"
        matches = any(
            re.search(
                pattern[0] if isinstance(pattern, tuple) else pattern,
                test_text,
                re.IGNORECASE,
            )
            for pattern in question_patterns
        )
        assert matches

    def test_agreement_patterns(self):
        """Test agreement detection patterns."""
        agreement_patterns = CUE_PHRASES.get("agreement", [])

        assert len(agreement_patterns) > 0

        # Test agreement
        test_text = "Yes, I agree"
        matches = any(
            re.search(
                pattern[0] if isinstance(pattern, tuple) else pattern,
                test_text,
                re.IGNORECASE,
            )
            for pattern in agreement_patterns
        )
        assert matches

    def test_disagreement_patterns(self):
        """Test disagreement detection patterns."""
        disagreement_patterns = CUE_PHRASES.get("disagreement", [])

        assert len(disagreement_patterns) > 0

        # Test disagreement
        test_text = "No, I don't think so"
        matches = any(
            re.search(
                pattern[0] if isinstance(pattern, tuple) else pattern,
                test_text,
                re.IGNORECASE,
            )
            for pattern in disagreement_patterns
        )
        assert matches

    def test_suggestion_patterns(self):
        """Test suggestion detection patterns."""
        suggestion_patterns = CUE_PHRASES.get("suggestion", [])

        assert len(suggestion_patterns) > 0

        # Test suggestion
        test_text = "Let's try this approach"
        matches = any(
            re.search(
                pattern[0] if isinstance(pattern, tuple) else pattern,
                test_text,
                re.IGNORECASE,
            )
            for pattern in suggestion_patterns
        )
        assert matches

    def test_pattern_confidence_scores(self):
        """Test that patterns include confidence scores."""
        for act_type, patterns in CUE_PHRASES.items():
            for pattern in patterns:
                if isinstance(pattern, tuple):
                    pattern_str, confidence = pattern
                    assert isinstance(confidence, (int, float))
                    assert 0 <= confidence <= 1
                else:
                    # Pattern without confidence (should be rare)
                    assert isinstance(pattern, str)
