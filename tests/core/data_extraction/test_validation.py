"""
Tests for data extraction validation (DataValidationError, field and domain validators).
"""

# mypy: disallow_untyped_defs=false

import pytest

from transcriptx.core.data_extraction.validation import (
    DataValidationError,
    validate_speaker_data,
    validate_numeric_field,
    validate_string_field,
    validate_list_field,
    validate_dict_field,
    validate_sentiment_data,
    validate_emotion_data,
    validate_topic_data,
    validate_entity_data,
    validate_tic_data,
    validate_semantic_data,
    validate_interaction_data,
    validate_performance_data,
)


class TestDataValidationError:
    """Tests for DataValidationError exception."""

    def test_message_and_data(self):
        err = DataValidationError("bad value", {"key": 1})
        assert str(err) == "bad value"
        assert err.message == "bad value"
        assert err.data == {"key": 1}

    def test_data_optional(self):
        err = DataValidationError("missing")
        assert err.data is None


class TestValidateSpeakerData:
    """Tests for validate_speaker_data."""

    def test_valid_without_required_fields(self):
        assert validate_speaker_data({}) is True

    def test_valid_with_required_fields_present(self):
        assert validate_speaker_data({"a": 1, "b": 2}, ["a", "b"]) is True

    def test_raises_when_not_dict(self):
        with pytest.raises(DataValidationError, match="must be a dictionary"):
            validate_speaker_data([])

    def test_raises_when_required_field_missing(self):
        with pytest.raises(DataValidationError, match="Required field 'x' is missing"):
            validate_speaker_data({"a": 1}, ["a", "x"])


class TestValidateNumericField:
    """Tests for validate_numeric_field."""

    def test_allows_none(self):
        assert validate_numeric_field(None, "x") is True

    def test_valid_without_bounds(self):
        assert validate_numeric_field(1.5, "x") is True
        assert validate_numeric_field(0, "x") is True

    def test_valid_with_min_max(self):
        assert validate_numeric_field(0.5, "x", 0.0, 1.0) is True

    def test_raises_when_not_numeric(self):
        with pytest.raises(DataValidationError, match="must be numeric"):
            validate_numeric_field("abc", "x")

    def test_raises_when_below_min(self):
        with pytest.raises(DataValidationError, match="must be >= 0"):
            validate_numeric_field(-0.1, "x", 0.0)

    def test_raises_when_above_max(self):
        with pytest.raises(DataValidationError, match="must be <= 1"):
            validate_numeric_field(1.1, "x", 0.0, 1.0)


class TestValidateStringField:
    """Tests for validate_string_field."""

    def test_allows_none(self):
        assert validate_string_field(None, "x") is True

    def test_valid_no_constraints(self):
        assert validate_string_field("hello", "x") is True

    def test_valid_with_max_length(self):
        assert validate_string_field("ab", "x", max_length=5) is True

    def test_valid_with_allowed_values(self):
        assert validate_string_field("a", "x", allowed_values=["a", "b"]) is True

    def test_raises_when_not_string(self):
        with pytest.raises(DataValidationError, match="must be a string"):
            validate_string_field(123, "x")

    def test_raises_when_exceeds_max_length(self):
        with pytest.raises(DataValidationError, match="<= 2 characters"):
            validate_string_field("abc", "x", max_length=2)

    def test_raises_when_not_in_allowed_values(self):
        with pytest.raises(DataValidationError, match="must be one of"):
            validate_string_field("c", "x", allowed_values=["a", "b"])


class TestValidateListField:
    """Tests for validate_list_field."""

    def test_allows_none(self):
        assert validate_list_field(None, "x") is True

    def test_valid_no_constraints(self):
        assert validate_list_field([1, 2], "x") is True

    def test_valid_with_min_max_length(self):
        assert validate_list_field([1, 2, 3], "x", min_length=2, max_length=5) is True

    def test_raises_when_not_list(self):
        with pytest.raises(DataValidationError, match="must be a list"):
            validate_list_field("not a list", "x")

    def test_raises_when_below_min_length(self):
        with pytest.raises(DataValidationError, match="at least 2 items"):
            validate_list_field([1], "x", min_length=2)

    def test_raises_when_above_max_length(self):
        with pytest.raises(DataValidationError, match="at most 2 items"):
            validate_list_field([1, 2, 3], "x", max_length=2)


class TestValidateDictField:
    """Tests for validate_dict_field."""

    def test_allows_none(self):
        assert validate_dict_field(None, "x") is True

    def test_valid_no_required_keys(self):
        assert validate_dict_field({"a": 1}, "x") is True

    def test_valid_with_required_keys(self):
        assert (
            validate_dict_field({"a": 1, "b": 2}, "x", required_keys=["a", "b"]) is True
        )

    def test_raises_when_not_dict(self):
        with pytest.raises(DataValidationError, match="must be a dictionary"):
            validate_dict_field([], "x")

    def test_raises_when_required_key_missing(self):
        with pytest.raises(DataValidationError, match="must contain key 'b'"):
            validate_dict_field({"a": 1}, "x", required_keys=["a", "b"])


class TestValidateSentimentData:
    """Tests for validate_sentiment_data."""

    def test_valid_minimal(self):
        data = {"average_sentiment_score": 0.0}
        assert validate_sentiment_data(data) is True

    def test_valid_full(self):
        data = {
            "average_sentiment_score": 0.1,
            "sentiment_volatility": 0.2,
            "sentiment_consistency_score": 0.8,
            "dominant_sentiment_pattern": "neutral",
            "positive_trigger_words": ["good"],
            "negative_trigger_words": ["bad"],
            "sentiment_trends": {},
        }
        assert validate_sentiment_data(data) is True

    def test_raises_when_required_field_missing(self):
        with pytest.raises(DataValidationError, match="Required field"):
            validate_sentiment_data({})

    def test_raises_when_score_out_of_range(self):
        with pytest.raises(DataValidationError, match="average_sentiment_score"):
            validate_sentiment_data({"average_sentiment_score": 2.0})


class TestValidateEmotionData:
    """Tests for validate_emotion_data."""

    def test_valid_minimal(self):
        assert validate_emotion_data({}) is True

    def test_valid_with_fields(self):
        data = {
            "dominant_emotion": "neutral",
            "emotional_stability": 0.5,
            "emotional_reactivity": 0.3,
            "emotion_consistency": 0.7,
            "emotion_distribution": {},
            "emotion_transition_patterns": {},
        }
        assert validate_emotion_data(data) is True

    def test_raises_when_numeric_out_of_range(self):
        with pytest.raises(DataValidationError, match="emotional_stability"):
            validate_emotion_data({"emotional_stability": 1.5})


class TestValidateTopicData:
    """Tests for validate_topic_data."""

    def test_valid_empty(self):
        assert validate_topic_data({}) is True

    def test_valid_with_fields(self):
        data = {
            "topic_engagement_style": "balanced",
            "preferred_topics": {},
            "topic_expertise_scores": {},
            "topic_contribution_patterns": {},
            "topic_evolution_trends": {},
        }
        assert validate_topic_data(data) is True

    def test_raises_when_string_too_long(self):
        with pytest.raises(DataValidationError, match="<= 50 characters"):
            validate_topic_data({"topic_engagement_style": "x" * 51})


class TestValidateEntityData:
    """Tests for validate_entity_data."""

    def test_valid_empty(self):
        assert validate_entity_data({}) is True

    def test_valid_with_dict_fields(self):
        data = {
            "entity_expertise_domains": {},
            "frequently_mentioned_entities": {},
            "entity_network": {},
            "entity_sentiment_patterns": {},
            "entity_evolution": {},
        }
        assert validate_entity_data(data) is True

    def test_raises_when_field_not_dict(self):
        with pytest.raises(DataValidationError, match="must be a dictionary"):
            validate_entity_data({"entity_network": "not a dict"})


class TestValidateTicData:
    """Tests for validate_tic_data."""

    def test_valid_empty(self):
        assert validate_tic_data({}) is True

    def test_valid_with_dict_fields(self):
        data = {
            "tic_frequency": {},
            "tic_types": {},
            "tic_context_patterns": {},
            "tic_evolution": {},
            "tic_reduction_goals": {},
            "tic_confidence_indicators": {},
        }
        assert validate_tic_data(data) is True

    def test_raises_when_field_not_dict(self):
        with pytest.raises(DataValidationError, match="must be a dictionary"):
            validate_tic_data({"tic_frequency": []})


class TestValidateSemanticData:
    """Tests for validate_semantic_data."""

    def test_valid_empty(self):
        assert validate_semantic_data({}) is True

    def test_valid_with_fields(self):
        data = {
            "vocabulary_sophistication": 0.5,
            "semantic_consistency": 0.6,
            "semantic_fingerprint": {},
            "agreement_patterns": {},
            "disagreement_patterns": {},
            "semantic_evolution": {},
        }
        assert validate_semantic_data(data) is True

    def test_raises_when_numeric_out_of_range(self):
        with pytest.raises(DataValidationError, match="vocabulary_sophistication"):
            validate_semantic_data({"vocabulary_sophistication": -0.1})


class TestValidateInteractionData:
    """Tests for validate_interaction_data."""

    def test_valid_empty(self):
        assert validate_interaction_data({}) is True

    def test_valid_with_fields(self):
        data = {
            "interaction_style": "collaborative",
            "influence_score": 0.5,
            "collaboration_score": 0.7,
            "interruption_patterns": {},
            "response_patterns": {},
            "interaction_network": {},
        }
        assert validate_interaction_data(data) is True

    def test_raises_when_score_out_of_range(self):
        with pytest.raises(DataValidationError, match="influence_score"):
            validate_interaction_data({"influence_score": 1.5})


class TestValidatePerformanceData:
    """Tests for validate_performance_data."""

    def test_valid_empty(self):
        assert validate_performance_data({}) is True

    def test_valid_with_fields(self):
        data = {
            "speaking_style": "clear",
            "participation_patterns": {},
            "performance_metrics": {},
            "improvement_areas": {},
            "strengths": {},
        }
        assert validate_performance_data(data) is True

    def test_raises_when_field_not_dict(self):
        with pytest.raises(DataValidationError, match="must be a dictionary"):
            validate_performance_data({"performance_metrics": []})
