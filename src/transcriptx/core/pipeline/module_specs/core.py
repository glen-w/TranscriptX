"""Domain-specific module registry definition builders."""

from __future__ import annotations

from typing import Dict, List

from transcriptx.core.domain.module_requirements import Requirement


def build_core_module_definitions(
    default_requirements: List[Requirement],
) -> Dict[str, Dict]:
    return {
        "stats": {
            "description": "Statistical Analysis",
            "dependencies": [],
            "category": "light",
            "determinism_tier": "T0",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
        },
        "tics": {
            "description": "Verbal Tics Analysis",
            "dependencies": [],
            "category": "light",
            "determinism_tier": "T0",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
        },
        "insight_eligibility": {
            "description": "Shared content-vs-style insight eligibility pipeline",
            "dependencies": ["tics"],
            "category": "light",
            "determinism_tier": "T0",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
        },
        "temporal_dynamics": {
            "description": "Temporal Dynamics Analysis",
            "dependencies": [],
            "category": "medium",
            "determinism_tier": "T1",
            "requirements": [
                Requirement.SEGMENTS,
                Requirement.SEGMENT_TIMESTAMPS,
                Requirement.SPEAKER_LABELS,
            ],
            "enhancements": [],
        },
        "pauses": {
            "description": "Silence and Timing Analysis",
            "dependencies": [],
            "category": "light",
            "determinism_tier": "T0",
            "requirements": [
                Requirement.SEGMENTS,
                Requirement.SEGMENT_TIMESTAMPS,
                Requirement.SPEAKER_LABELS,
            ],
            "enhancements": [],
        },
        "momentum": {
            "description": "Stall/Flow Index Analysis",
            "dependencies": ["pauses"],
            "category": "medium",
            "determinism_tier": "T0",
            "requirements": [
                Requirement.SEGMENTS,
                Requirement.SEGMENT_TIMESTAMPS,
                Requirement.SPEAKER_LABELS,
            ],
            "enhancements": [],
        },
        "moments": {
            "description": "Ranked Moments Worth Revisiting",
            "dependencies": ["momentum"],
            "category": "light",
            "determinism_tier": "T0",
            "requirements": [Requirement.SEGMENTS, Requirement.SEGMENT_TIMESTAMPS],
            "enhancements": [],
        },
    }
