"""
Data validation utilities for TranscriptX data extraction.

This module provides validation functions and custom exceptions for ensuring
data quality and consistency in the data extraction process.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DataValidationError(Exception):
    """Custom exception for data validation errors."""

    def __init__(self, message: str, data: Optional[Dict[str, Any]] = None):
        """
        Initialize the validation error.

        Args:
            message: Error message
            data: Optional data that caused the validation error
        """
        super().__init__(message)
        self.message = message
        self.data = data


def validate_speaker_data(
    data: Dict[str, Any], required_fields: List[str] = None
) -> bool:
    """
    Validate speaker data for required fields and data types.

    Args:
        data: Speaker data to validate
        required_fields: List of required field names

    Returns:
        True if data is valid

    Raises:
        DataValidationError: If validation fails
    """
    if not isinstance(data, dict):
        raise DataValidationError("Data must be a dictionary", data)

    if required_fields:
        for field in required_fields:
            if field not in data:
                raise DataValidationError(f"Required field '{field}' is missing", data)

    return True


def validate_numeric_field(
    value: Any,
    field_name: str,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> bool:
    """
    Validate a numeric field.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        min_value: Minimum allowed value
        max_value: Maximum allowed value

    Returns:
        True if value is valid

    Raises:
        DataValidationError: If validation fails
    """
    if value is None:
        return True  # Allow None values

    try:
        float_value = float(value)
    except (ValueError, TypeError):
        raise DataValidationError(
            f"Field '{field_name}' must be numeric", {"value": value}
        )

    if min_value is not None and float_value < min_value:
        raise DataValidationError(
            f"Field '{field_name}' must be >= {min_value}", {"value": float_value}
        )

    if max_value is not None and float_value > max_value:
        raise DataValidationError(
            f"Field '{field_name}' must be <= {max_value}", {"value": float_value}
        )

    return True


def validate_string_field(
    value: Any,
    field_name: str,
    max_length: Optional[int] = None,
    allowed_values: Optional[List[str]] = None,
) -> bool:
    """
    Validate a string field.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        max_length: Maximum allowed length
        allowed_values: List of allowed values

    Returns:
        True if value is valid

    Raises:
        DataValidationError: If validation fails
    """
    if value is None:
        return True  # Allow None values

    if not isinstance(value, str):
        raise DataValidationError(
            f"Field '{field_name}' must be a string", {"value": value}
        )

    if max_length is not None and len(value) > max_length:
        raise DataValidationError(
            f"Field '{field_name}' must be <= {max_length} characters", {"value": value}
        )

    if allowed_values is not None and value not in allowed_values:
        raise DataValidationError(
            f"Field '{field_name}' must be one of {allowed_values}", {"value": value}
        )

    return True


def validate_list_field(
    value: Any,
    field_name: str,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
) -> bool:
    """
    Validate a list field.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        min_length: Minimum allowed length
        max_length: Maximum allowed length

    Returns:
        True if value is valid

    Raises:
        DataValidationError: If validation fails
    """
    if value is None:
        return True  # Allow None values

    if not isinstance(value, list):
        raise DataValidationError(
            f"Field '{field_name}' must be a list", {"value": value}
        )

    if min_length is not None and len(value) < min_length:
        raise DataValidationError(
            f"Field '{field_name}' must have at least {min_length} items",
            {"value": value},
        )

    if max_length is not None and len(value) > max_length:
        raise DataValidationError(
            f"Field '{field_name}' must have at most {max_length} items",
            {"value": value},
        )

    return True


def validate_dict_field(
    value: Any, field_name: str, required_keys: Optional[List[str]] = None
) -> bool:
    """
    Validate a dictionary field.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        required_keys: List of required keys

    Returns:
        True if value is valid

    Raises:
        DataValidationError: If validation fails
    """
    if value is None:
        return True  # Allow None values

    if not isinstance(value, dict):
        raise DataValidationError(
            f"Field '{field_name}' must be a dictionary", {"value": value}
        )

    if required_keys:
        for key in required_keys:
            if key not in value:
                raise DataValidationError(
                    f"Field '{field_name}' must contain key '{key}'", {"value": value}
                )

    return True


def validate_sentiment_data(data: Dict[str, Any]) -> bool:
    """
    Validate sentiment analysis data.

    Args:
        data: Sentiment data to validate

    Returns:
        True if data is valid

    Raises:
        DataValidationError: If validation fails
    """
    required_fields = ["average_sentiment_score"]

    # Validate required fields
    validate_speaker_data(data, required_fields)

    # Validate numeric fields
    validate_numeric_field(
        data.get("average_sentiment_score"), "average_sentiment_score", -1.0, 1.0
    )
    validate_numeric_field(
        data.get("sentiment_volatility"), "sentiment_volatility", 0.0
    )
    validate_numeric_field(
        data.get("sentiment_consistency_score"), "sentiment_consistency_score", 0.0, 1.0
    )

    # Validate string fields
    validate_string_field(
        data.get("dominant_sentiment_pattern"), "dominant_sentiment_pattern", 50
    )

    # Validate list fields
    validate_list_field(data.get("positive_trigger_words"), "positive_trigger_words")
    validate_list_field(data.get("negative_trigger_words"), "negative_trigger_words")

    # Validate dict fields
    validate_dict_field(data.get("sentiment_trends"), "sentiment_trends")

    return True


def validate_emotion_data(data: Dict[str, Any]) -> bool:
    """
    Validate emotion analysis data.

    Args:
        data: Emotion data to validate

    Returns:
        True if data is valid

    Raises:
        DataValidationError: If validation fails
    """
    # Validate string fields
    validate_string_field(data.get("dominant_emotion"), "dominant_emotion", 50)

    # Validate numeric fields
    validate_numeric_field(
        data.get("emotional_stability"), "emotional_stability", 0.0, 1.0
    )
    validate_numeric_field(
        data.get("emotional_reactivity"), "emotional_reactivity", 0.0, 1.0
    )
    validate_numeric_field(
        data.get("emotion_consistency"), "emotion_consistency", 0.0, 1.0
    )

    # Validate dict fields
    validate_dict_field(data.get("emotion_distribution"), "emotion_distribution")
    validate_dict_field(
        data.get("emotion_transition_patterns"), "emotion_transition_patterns"
    )

    return True


def validate_topic_data(data: Dict[str, Any]) -> bool:
    """
    Validate topic modeling data.

    Args:
        data: Topic data to validate

    Returns:
        True if data is valid

    Raises:
        DataValidationError: If validation fails
    """
    # Validate string fields
    validate_string_field(
        data.get("topic_engagement_style"), "topic_engagement_style", 50
    )

    # Validate dict fields
    validate_dict_field(data.get("preferred_topics"), "preferred_topics")
    validate_dict_field(data.get("topic_expertise_scores"), "topic_expertise_scores")
    validate_dict_field(
        data.get("topic_contribution_patterns"), "topic_contribution_patterns"
    )
    validate_dict_field(data.get("topic_evolution_trends"), "topic_evolution_trends")

    return True


def validate_entity_data(data: Dict[str, Any]) -> bool:
    """
    Validate entity analysis data.

    Args:
        data: Entity data to validate

    Returns:
        True if data is valid

    Raises:
        DataValidationError: If validation fails
    """
    # Validate dict fields
    validate_dict_field(
        data.get("entity_expertise_domains"), "entity_expertise_domains"
    )
    validate_dict_field(
        data.get("frequently_mentioned_entities"), "frequently_mentioned_entities"
    )
    validate_dict_field(data.get("entity_network"), "entity_network")
    validate_dict_field(
        data.get("entity_sentiment_patterns"), "entity_sentiment_patterns"
    )
    validate_dict_field(data.get("entity_evolution"), "entity_evolution")

    return True


def validate_tic_data(data: Dict[str, Any]) -> bool:
    """
    Validate verbal tics data.

    Args:
        data: Tic data to validate

    Returns:
        True if data is valid

    Raises:
        DataValidationError: If validation fails
    """
    # Validate dict fields
    validate_dict_field(data.get("tic_frequency"), "tic_frequency")
    validate_dict_field(data.get("tic_types"), "tic_types")
    validate_dict_field(data.get("tic_context_patterns"), "tic_context_patterns")
    validate_dict_field(data.get("tic_evolution"), "tic_evolution")
    validate_dict_field(data.get("tic_reduction_goals"), "tic_reduction_goals")
    validate_dict_field(
        data.get("tic_confidence_indicators"), "tic_confidence_indicators"
    )

    return True


def validate_semantic_data(data: Dict[str, Any]) -> bool:
    """
    Validate semantic similarity data.

    Args:
        data: Semantic data to validate

    Returns:
        True if data is valid

    Raises:
        DataValidationError: If validation fails
    """
    # Validate numeric fields
    validate_numeric_field(
        data.get("vocabulary_sophistication"), "vocabulary_sophistication", 0.0, 1.0
    )
    validate_numeric_field(
        data.get("semantic_consistency"), "semantic_consistency", 0.0, 1.0
    )

    # Validate dict fields
    validate_dict_field(data.get("semantic_fingerprint"), "semantic_fingerprint")
    validate_dict_field(data.get("agreement_patterns"), "agreement_patterns")
    validate_dict_field(data.get("disagreement_patterns"), "disagreement_patterns")
    validate_dict_field(data.get("semantic_evolution"), "semantic_evolution")

    return True


def validate_interaction_data(data: Dict[str, Any]) -> bool:
    """
    Validate interaction analysis data.

    Args:
        data: Interaction data to validate

    Returns:
        True if data is valid

    Raises:
        DataValidationError: If validation fails
    """
    # Validate string fields
    validate_string_field(data.get("interaction_style"), "interaction_style", 50)

    # Validate numeric fields
    validate_numeric_field(data.get("influence_score"), "influence_score", 0.0, 1.0)
    validate_numeric_field(
        data.get("collaboration_score"), "collaboration_score", 0.0, 1.0
    )

    # Validate dict fields
    validate_dict_field(data.get("interruption_patterns"), "interruption_patterns")
    validate_dict_field(data.get("response_patterns"), "response_patterns")
    validate_dict_field(data.get("interaction_network"), "interaction_network")

    return True


def validate_performance_data(data: Dict[str, Any]) -> bool:
    """
    Validate performance analysis data.

    Args:
        data: Performance data to validate

    Returns:
        True if data is valid

    Raises:
        DataValidationError: If validation fails
    """
    # Validate string fields
    validate_string_field(data.get("speaking_style"), "speaking_style", 50)

    # Validate dict fields
    validate_dict_field(data.get("participation_patterns"), "participation_patterns")
    validate_dict_field(data.get("performance_metrics"), "performance_metrics")
    validate_dict_field(data.get("improvement_areas"), "improvement_areas")
    validate_dict_field(data.get("strengths"), "strengths")

    return True
