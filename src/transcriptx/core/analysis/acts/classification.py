"""Classification helpers for dialogue act analysis."""

from __future__ import annotations

from typing import Any

from transcriptx.core.analysis.acts.config import ClassificationMethod, get_act_config
from transcriptx.core.analysis.acts.rules import rules_classify_utterance

# Global ML classifier instance to avoid repeated initialization
_ml_classifier_instance = None


def classify_utterance(
    text: str, context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Classify an utterance into a dialogue act type using the configured method.

    Args:
        text: The utterance text to classify
        context: Optional context dictionary containing previous utterances, speaker info, etc.

    Returns:
        Dictionary containing act type, confidence, method used, and probabilities
    """
    config = get_act_config()
    text_lower = text.lower().strip()

    # Skip empty or very short utterances
    if len(text_lower) < 2:
        return {
            "act_type": "acknowledgement",
            "confidence": 1.0,
            "method": "fallback",
            "probabilities": {"acknowledgement": 1.0},
        }

    # Use the configured classification method
    if config.method == ClassificationMethod.BOTH:
        return classify_with_both_methods(text, context)
    if config.method == ClassificationMethod.ML:
        return ml_classify_utterance(text, context)
    # RULES
    return rules_classify_utterance(text, context)


def classify_with_both_methods(
    text: str, context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Classify an utterance using both ML and rules methods.

    Args:
        text: The utterance text to classify
        context: Optional context dictionary

    Returns:
        Dictionary with both classification results
    """
    # Get both classifications
    ml_result = ml_classify_utterance(text, context)
    rules_result = rules_classify_utterance(text, context)

    # Determine which result to use as primary (higher confidence)
    primary_result = (
        ml_result
        if ml_result["confidence"] >= rules_result["confidence"]
        else rules_result
    )

    return {
        "act_type": primary_result["act_type"],
        "confidence": primary_result["confidence"],
        "method": "both",
        "probabilities": primary_result["probabilities"],
        "ml_result": ml_result,
        "rules_result": rules_result,
        "methods_agreed": ml_result["act_type"] == rules_result["act_type"],
        "confidence_difference": abs(
            ml_result["confidence"] - rules_result["confidence"]
        ),
    }


def reset_ml_classifier():
    """Reset the global ML classifier instance. Useful for testing or when configuration changes."""
    global _ml_classifier_instance
    _ml_classifier_instance = None


def ml_classify_utterance(
    text: str, context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Machine learning-based classification with graceful fallback.

    Args:
        text: The utterance text to classify
        context: Optional context dictionary

    Returns:
        Dictionary with classification results
    """
    global _ml_classifier_instance

    try:
        # Import here to avoid circular imports
        from transcriptx.core.analysis.acts.ml_classifier import create_ml_classifier

        # Use singleton pattern to avoid repeated initialization
        if _ml_classifier_instance is None:
            act_config = get_act_config()
            _ml_classifier_instance = create_ml_classifier(
                model_name=act_config.ml_model_name,
                use_context=act_config.use_context,
            )

        result = _ml_classifier_instance.classify_with_ml(text, context)

        return {
            "act_type": result.act_type,
            "confidence": result.confidence,
            "method": result.method,
            "probabilities": result.probabilities,
            "fallback_used": result.fallback_used,
        }
    except Exception as e:
        # Log the error and fallback to rules
        import logging

        logger = logging.getLogger(__name__)

        # Check if this is the expected estimators_ error
        if "estimators_" in str(e):
            logger.debug(f"ML models not trained, using rule-based fallback: {e}")
        else:
            logger.warning(f"ML classification failed, falling back to rules: {e}")

        # Fallback to rules if ML fails
        return rules_classify_utterance(text, context)
