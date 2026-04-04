"""Confidence scoring helpers for dialogue act classification."""

from __future__ import annotations

import re
from typing import Any


def adjust_confidence_for_context(
    act_type: str, confidence: float, context: dict[str, Any]
) -> float:
    """
    Adjust confidence score based on conversational context.

    Args:
        act_type: The act type being considered
        confidence: Current confidence score
        context: Context dictionary with conversation history

    Returns:
        Adjusted confidence score
    """
    # Get previous utterances (if available)
    previous_utterances = context.get("previous_utterances", [])
    # Boost confidence for follow-up questions
    if act_type == "question" and previous_utterances:
        last_utterance = previous_utterances[-1].lower()
        if any(word in last_utterance for word in ["because", "since", "as", "due to"]):
            confidence += 0.1  # Likely a follow-up question

    # Boost confidence for agreement/disagreement after statements
    if act_type in ["agreement", "disagreement"] and previous_utterances:
        last_utterance = previous_utterances[-1].lower()
        if any(
            word in last_utterance for word in ["think", "believe", "feel", "opinion"]
        ):
            confidence += 0.15  # Likely responding to an opinion

    # Boost confidence for clarification after complex statements
    if act_type == "clarification" and previous_utterances:
        last_utterance = previous_utterances[-1]
        if len(last_utterance.split()) > 10:  # Long utterance
            confidence += 0.1

    # Reduce confidence for certain acts in certain contexts
    if act_type == "greeting" and len(previous_utterances) > 5:
        confidence -= 0.2  # Less likely to be greeting mid-conversation

    if act_type == "farewell" and len(previous_utterances) < 3:
        confidence -= 0.3  # Less likely to be farewell early in conversation

    return max(0.0, min(1.0, confidence))  # Clamp between 0 and 1


def calculate_act_confidence(
    text: str, act: str, context: dict[str, Any] | None = None
) -> float:
    """
    Calculate confidence score for act classification.

    Args:
        text: The utterance text
        act: The classified act type
        context: Optional context dictionary

    Returns:
        Confidence score between 0.0 and 1.0
    """
    text_lower = text.lower().strip()

    # Base confidence from pattern matching
    base_confidence = 0.5

    # Check if act matches any patterns
    from transcriptx.core.analysis.acts.rules import CUE_PHRASES

    if act in CUE_PHRASES:
        for pattern, confidence in CUE_PHRASES[act]:
            if re.search(pattern, text_lower):
                base_confidence = max(base_confidence, confidence)
                # Boost for exact matches
                if re.match(pattern, text_lower):
                    base_confidence += 0.1

    # Context-based adjustments
    if context:
        # Boost confidence for clear context matches
        if context.get("previous_utterances"):
            last_utterance = context["previous_utterances"][-1].lower()

            # Question-response patterns
            if act == "response" and "?" in last_utterance:
                base_confidence += 0.2

            # Agreement/disagreement after opinions
            if act in ["agreement", "disagreement"] and any(
                word in last_utterance for word in ["think", "believe", "feel"]
            ):
                base_confidence += 0.15

        # Reduce confidence for unlikely patterns
        if act == "greeting" and context.get("utterance_index", 0) > 5:
            base_confidence -= 0.3

        if (
            act == "farewell"
            and context.get("utterance_index", 0)
            < context.get("total_utterances", 100) * 0.8
        ):
            base_confidence -= 0.3

    # Text length adjustments
    if len(text.split()) < 3:
        base_confidence -= 0.1  # Short utterances are harder to classify

    # Clamp between 0.0 and 1.0
    return max(0.0, min(1.0, base_confidence))
