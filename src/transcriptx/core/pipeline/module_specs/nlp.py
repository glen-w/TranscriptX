"""Domain-specific module registry definition builders."""

from __future__ import annotations

from typing import Dict, List

from transcriptx.core.domain.module_requirements import Requirement


def build_nlp_module_definitions(
    default_requirements: List[Requirement],
) -> Dict[str, Dict]:
    return {
        "emotion": {
            "description": "Emotion-associated vocabulary (NRC lexicon)",
            "dependencies": [],
            "category": "medium",
            "determinism_tier": "T1",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
            "required_extras": ["emotion_lexical"],
        },
        "contextual_emotion": {
            "description": "Contextual emotion (broad classifier, experimental)",
            "dependencies": [],
            "category": "heavy",
            "determinism_tier": "T2",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
            "required_extras": ["emotion_transformers"],
        },
        "fine_grained_emotion": {
            "description": "Fine-grained multi-label emotion (experimental)",
            "dependencies": [],
            "category": "heavy",
            "determinism_tier": "T2",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
            "required_extras": ["emotion_transformers"],
        },
        "entity_sentiment": {
            "description": "Entity-based Sentiment Analysis",
            "dependencies": ["ner", "sentiment"],
            "category": "heavy",
            "determinism_tier": "T1",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
            "required_extras": ["nlp"],
        },
        "ner": {
            "description": "Named Entity Recognition",
            "dependencies": [],
            "category": "medium",
            "determinism_tier": "T1",
            "requirements": default_requirements,
            "enhancements": [],
            "required_extras": ["nlp"],
        },
        "sentiment": {
            "description": "Sentiment Analysis",
            "dependencies": [],
            "category": "medium",
            "determinism_tier": "T1",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
        },
        "epistemic_markers": {
            "description": "Hedging / certainty / epistemic markers",
            "dependencies": [],
            "category": "light",
            "determinism_tier": "T0",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
            "gate_on_turn_taking_speakers": True,
        },
    }
