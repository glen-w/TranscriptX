"""Domain-specific module registry definition builders."""

from __future__ import annotations

from typing import Dict, List

from transcriptx.core.domain.module_requirements import Requirement


def build_conversation_module_definitions(
    default_requirements: List[Requirement],
) -> Dict[str, Dict]:
    return {
        "acts": {
            "description": "Dialogue Act Classification",
            "dependencies": [],
            "category": "medium",
            "determinism_tier": "T0",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
        },
        "conversation_loops": {
            "description": "Conversation Loop Detection",
            "dependencies": [],
            "category": "light",
            "determinism_tier": "T0",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
            "requires_multiple_speakers": True,
        },
        "contagion": {
            "description": "Emotional Contagion Detection",
            "dependencies": ["emotion"],
            "optional_dependencies": ["contextual_emotion"],
            "category": "heavy",
            "determinism_tier": "T1",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
            "requires_multiple_speakers": True,
            "required_extras": ["emotion_lexical"],
        },
        "affect_tension": {
            "description": "Emotion + Sentiment mismatch and tension indices",
            "dependencies": ["emotion", "sentiment"],
            "optional_dependencies": ["contextual_emotion"],
            "category": "medium",
            "determinism_tier": "T1",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
            "required_extras": ["emotion_lexical"],
        },
        "interactions": {
            "description": "Speaker Interaction Analysis",
            "dependencies": [],
            "category": "medium",
            "determinism_tier": "T0",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
            "requires_multiple_speakers": True,
        },
        "echoes": {
            "description": "Quote/Echo/Paraphrase Detection",
            "dependencies": [],
            "category": "medium",
            "determinism_tier": "T1",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
            "requires_multiple_speakers": True,
        },
        "politeness": {
            "description": "Politeness / formality / directiveness markers",
            "dependencies": [],
            "category": "light",
            "determinism_tier": "T0",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
        },
    }
