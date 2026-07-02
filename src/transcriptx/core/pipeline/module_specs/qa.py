"""Domain-specific module registry definition builders."""

from __future__ import annotations

from typing import Dict, List

from transcriptx.core.domain.module_requirements import Requirement


def build_qa_module_definitions(
    default_requirements: List[Requirement],
) -> Dict[str, Dict]:
    return {
        "understandability": {
            "description": "Understandability Analysis",
            "dependencies": [],
            "category": "medium",
            "determinism_tier": "T0",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
            "gate_on_turn_taking_speakers": True,
        },
        "qa_analysis": {
            "description": "Question-Answer Pairing and Response Quality",
            "dependencies": ["acts"],
            "category": "medium",
            "determinism_tier": "T1",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
            "requires_multiple_speakers": True,
        },
    }
