"""Domain-specific module registry definition builders."""

from __future__ import annotations

from typing import Dict, List

from transcriptx.core.domain.module_requirements import Requirement


def build_nlp_module_definitions(
    default_requirements: List[Requirement],
) -> Dict[str, Dict]:
    return {
        "emotion": {
            "description": "Emotion Analysis",
            "dependencies": [],
            "category": "medium",
            "determinism_tier": "T1",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
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
    }
