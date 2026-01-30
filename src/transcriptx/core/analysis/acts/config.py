"""
Configuration for Dialogue Act Classification in TranscriptX.

This module provides configuration settings for:
1. Rule-based classification parameters
2. Machine learning model settings
3. Context window sizes
4. Confidence thresholds
5. Act type definitions and mappings
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ClassificationMethod(Enum):
    """Available classification methods."""

    RULES = "rules"
    ML = "ml"
    BOTH = "both"


class ContextWindowType(Enum):
    """Types of context windows."""

    FIXED = "fixed"
    DYNAMIC = "dynamic"
    SLIDING = "sliding"


@dataclass
class ActClassificationConfig:
    """Configuration for dialogue act classification."""

    # Classification method
    method: ClassificationMethod = ClassificationMethod.BOTH

    # Context settings
    use_context: bool = True
    context_window_size: int = 3
    context_window_type: ContextWindowType = ContextWindowType.SLIDING
    include_speaker_info: bool = True
    include_timing_info: bool = False

    # Confidence thresholds
    min_confidence: float = 0.7
    high_confidence_threshold: float = 0.9
    ensemble_weight_transformer: float = 0.5
    ensemble_weight_ml: float = 0.3
    ensemble_weight_rules: float = 0.2

    # Machine learning settings
    ml_model_name: str = "bert-base-uncased"
    ml_use_gpu: bool = False
    ml_batch_size: int = 32
    ml_max_length: int = 512

    # Rule-based settings
    rules_use_enhanced_patterns: bool = True
    rules_use_fallback_logic: bool = True
    rules_confidence_boost_exact_match: float = 0.1
    rules_context_boost_factor: float = 0.15

    # Output settings
    include_confidence_scores: bool = True
    include_probabilities: bool = True
    include_classification_method: bool = True
    save_detailed_analysis: bool = True

    # Both methods settings
    run_both_methods: bool = True
    create_separate_outputs: bool = True
    both_methods_output_dir: str = "both_methods"
    compare_results: bool = True
    include_comparison_analysis: bool = True

    # Performance settings
    enable_caching: bool = True
    cache_size: int = 1000
    # Parallel processing removed - using DAG pipeline instead
    # Max workers removed - using DAG pipeline instead


# Default configuration
DEFAULT_ACT_CONFIG = ActClassificationConfig()


# Act type definitions and descriptions
ACT_TYPE_DEFINITIONS = {
    "question": {
        "description": "Utterances that seek information or clarification",
        "examples": [
            "What time is it?",
            "Do you know the answer?",
            "How does this work?",
        ],
        "confidence_boosters": [
            "?",
            "what",
            "why",
            "how",
            "when",
            "where",
            "who",
            "which",
        ],
        "confidence_reducers": ["statement", "long_utterance"],
    },
    "suggestion": {
        "description": "Utterances that propose actions or ideas",
        "examples": ["Let's try this approach", "I suggest we...", "How about we..."],
        "confidence_boosters": [
            "let's",
            "we should",
            "i suggest",
            "how about",
            "maybe we",
        ],
        "confidence_reducers": ["agreement", "disagreement"],
    },
    "agreement": {
        "description": "Utterances that express agreement or approval",
        "examples": ["Yes, that's right", "I agree", "Sounds good", "Absolutely"],
        "confidence_boosters": [
            "yes",
            "agree",
            "right",
            "good",
            "absolutely",
            "exactly",
        ],
        "confidence_reducers": ["disagreement", "question"],
    },
    "disagreement": {
        "description": "Utterances that express disagreement or disapproval",
        "examples": ["No, I don't think so", "I disagree", "That's not right"],
        "confidence_boosters": ["no", "disagree", "not", "wrong", "but", "however"],
        "confidence_reducers": ["agreement", "question"],
    },
    "clarification": {
        "description": "Utterances that seek clarification or explanation",
        "examples": ["What do you mean?", "Can you explain?", "I don't understand"],
        "confidence_boosters": [
            "what do you mean",
            "explain",
            "clarify",
            "don't understand",
        ],
        "confidence_reducers": ["statement", "greeting"],
    },
    "feedback": {
        "description": "Utterances that provide feedback or acknowledgment",
        "examples": ["That's interesting", "Good point", "I see what you mean"],
        "confidence_boosters": [
            "interesting",
            "good point",
            "see what you mean",
            "noted",
        ],
        "confidence_reducers": ["question", "command"],
    },
    "response": {
        "description": "Simple responses or acknowledgments",
        "examples": ["Okay", "Sure", "Yeah", "Right"],
        "confidence_boosters": ["okay", "sure", "yeah", "right", "uh-huh"],
        "confidence_reducers": ["long_utterance", "complex_structure"],
    },
    "greeting": {
        "description": "Utterances that greet or welcome",
        "examples": ["Hello", "Hi there", "Good morning", "Nice to see you"],
        "confidence_boosters": ["hello", "hi", "good morning", "greetings"],
        "confidence_reducers": ["mid_conversation", "long_utterance"],
    },
    "farewell": {
        "description": "Utterances that say goodbye or end conversation",
        "examples": ["Goodbye", "See you later", "Take care", "Bye"],
        "confidence_boosters": ["goodbye", "see you", "bye", "farewell"],
        "confidence_reducers": ["early_conversation", "question"],
    },
    "acknowledgement": {
        "description": "Non-verbal or minimal acknowledgments",
        "examples": ["Uh-huh", "Mhm", "Nod", "Shaking head"],
        "confidence_boosters": ["uh-huh", "mhm", "nod", "shaking"],
        "confidence_reducers": ["long_utterance", "complex_structure"],
    },
    "command": {
        "description": "Utterances that give orders or instructions",
        "examples": ["Do this", "Go there", "Tell me", "Stop"],
        "confidence_boosters": ["do this", "go", "tell", "stop", "wait"],
        "confidence_reducers": ["question", "suggestion"],
    },
    "apology": {
        "description": "Utterances that express apology or regret",
        "examples": ["I'm sorry", "My apologies", "Excuse me", "I made a mistake"],
        "confidence_boosters": ["sorry", "apologize", "excuse", "mistake"],
        "confidence_reducers": ["greeting", "farewell"],
    },
    "gratitude": {
        "description": "Utterances that express thanks or appreciation",
        "examples": ["Thank you", "Thanks", "I appreciate it", "Grateful"],
        "confidence_boosters": ["thank", "thanks", "appreciate", "grateful"],
        "confidence_reducers": ["question", "command"],
    },
    "statement": {
        "description": "Informative or declarative utterances",
        "examples": ["I think...", "The fact is...", "In my opinion..."],
        "confidence_boosters": ["i think", "fact is", "opinion", "believe"],
        "confidence_reducers": ["question", "command"],
    },
    "interruption": {
        "description": "Utterances that interrupt or overlap",
        "examples": ["Wait", "Stop", "Hold on", "Excuse me"],
        "confidence_boosters": ["wait", "stop", "hold on", "excuse me"],
        "confidence_reducers": ["long_utterance", "statement"],
    },
    "hesitation": {
        "description": "Utterances with filler words or pauses",
        "examples": ["Um", "Uh", "Well", "You know"],
        "confidence_boosters": ["um", "uh", "well", "you know", "like"],
        "confidence_reducers": ["long_utterance", "complex_structure"],
    },
    "emphasis": {
        "description": "Utterances with emphasis or intensity",
        "examples": ["Really", "Very", "Extremely", "Absolutely"],
        "confidence_boosters": ["really", "very", "extremely", "absolutely"],
        "confidence_reducers": ["neutral_tone", "short_utterance"],
    },
    "uncertainty": {
        "description": "Utterances expressing uncertainty or doubt",
        "examples": ["Maybe", "Perhaps", "I'm not sure", "Might"],
        "confidence_boosters": ["maybe", "perhaps", "not sure", "might", "could"],
        "confidence_reducers": ["certainty", "agreement"],
    },
}


# Context patterns for confidence adjustment
CONTEXT_PATTERNS = {
    "question_response": {
        "pattern": r"\?",
        "boost_acts": ["response", "answer"],
        "boost_factor": 0.2,
    },
    "opinion_response": {
        "pattern": r"\b(think|believe|feel|opinion)\b",
        "boost_acts": ["agreement", "disagreement"],
        "boost_factor": 0.15,
    },
    "complex_statement": {
        "pattern": r".{50,}",  # Long utterances
        "boost_acts": ["clarification", "feedback"],
        "boost_factor": 0.1,
    },
    "greeting_context": {
        "pattern": r"conversation_start",
        "boost_acts": ["greeting"],
        "boost_factor": 0.3,
    },
    "farewell_context": {
        "pattern": r"conversation_end",
        "boost_acts": ["farewell"],
        "boost_factor": 0.3,
    },
}


def get_act_config() -> ActClassificationConfig:
    """
    Get the current act classification configuration.

    This function now reads from the main config system's active profile.
    """
    from transcriptx.core.utils.config import get_config

    config = get_config()
    acts_config = config.analysis.acts

    # Convert ActsConfig to ActClassificationConfig for backward compatibility
    act_config = ActClassificationConfig()
    act_config.method = (
        ClassificationMethod(acts_config.method)
        if hasattr(ClassificationMethod, acts_config.method.upper())
        else ClassificationMethod.BOTH
    )
    act_config.use_context = acts_config.use_context
    act_config.context_window_size = acts_config.context_window_size
    act_config.context_window_type = (
        ContextWindowType(acts_config.context_window_type)
        if hasattr(ContextWindowType, acts_config.context_window_type.upper())
        else ContextWindowType.SLIDING
    )
    act_config.include_speaker_info = acts_config.include_speaker_info
    act_config.include_timing_info = acts_config.include_timing_info
    act_config.min_confidence = acts_config.min_confidence
    act_config.high_confidence_threshold = acts_config.high_confidence_threshold
    act_config.ensemble_weight_transformer = acts_config.ensemble_weight_transformer
    act_config.ensemble_weight_ml = acts_config.ensemble_weight_ml
    act_config.ensemble_weight_rules = acts_config.ensemble_weight_rules
    act_config.ml_model_name = acts_config.ml_model_name
    act_config.ml_use_gpu = acts_config.ml_use_gpu
    act_config.ml_batch_size = acts_config.ml_batch_size
    act_config.ml_max_length = acts_config.ml_max_length
    act_config.rules_use_enhanced_patterns = acts_config.rules_use_enhanced_patterns
    act_config.rules_use_fallback_logic = acts_config.rules_use_fallback_logic
    act_config.rules_confidence_boost_exact_match = (
        acts_config.rules_confidence_boost_exact_match
    )
    act_config.rules_context_boost_factor = acts_config.rules_context_boost_factor
    act_config.enable_caching = acts_config.enable_caching
    act_config.cache_size = acts_config.cache_size

    return act_config


def update_act_config(**kwargs) -> ActClassificationConfig:
    """
    Update the act classification configuration.

    Note: This now updates the main config system's acts config.
    """
    from transcriptx.core.utils.config import get_config

    config = get_config()
    acts_config = config.analysis.acts

    for key, value in kwargs.items():
        if hasattr(acts_config, key):
            setattr(acts_config, key, value)

    # Return updated config via get_act_config
    return get_act_config()


def get_act_definition(act_type: str) -> dict[str, Any]:
    """Get the definition and metadata for an act type."""
    return ACT_TYPE_DEFINITIONS.get(act_type, {})


def get_all_act_types() -> list[str]:
    """Get all available act types."""
    return list(ACT_TYPE_DEFINITIONS.keys())


def get_confidence_boosters(act_type: str) -> list[str]:
    """Get confidence boosters for an act type."""
    definition = get_act_definition(act_type)
    return definition.get("confidence_boosters", [])


def get_confidence_reducers(act_type: str) -> list[str]:
    """Get confidence reducers for an act type."""
    definition = get_act_definition(act_type)
    return definition.get("confidence_reducers", [])
