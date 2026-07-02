"""Domain-specific module registry definition builders."""

from __future__ import annotations

from typing import Dict, List

from transcriptx.core.domain.module_requirements import Enhancement, Requirement


def build_exports_module_definitions(
    default_requirements: List[Requirement],
) -> Dict[str, Dict]:
    return {
        "transcript_output": {
            "description": "Generate human readable transcripts",
            "dependencies": [],
            "category": "light",
            "determinism_tier": "T0",
            "requirements": default_requirements,
            "enhancements": [Enhancement.SPEAKER_DISPLAY_NAMES],
        },
        "simplified_transcript": {
            "description": "Simplified transcript (tics, agreements, repetitions removed)",
            "dependencies": [],
            "category": "light",
            "determinism_tier": "T0",
            "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
            "enhancements": [],
        },
    }
