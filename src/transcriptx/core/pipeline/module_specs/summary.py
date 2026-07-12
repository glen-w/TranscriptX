"""Domain-specific module registry definition builders."""

from __future__ import annotations

from typing import Dict, List

from transcriptx.core.domain.module_requirements import Requirement


def build_summary_module_definitions(
    default_requirements: List[Requirement],
) -> Dict[str, Dict]:
    return {
        "highlights": {
            "description": "Highlights and conflict moments (quote-forward)",
            "dependencies": ["insight_eligibility"],
            "category": "light",
            "determinism_tier": "T0",
            "requirements": [
                Requirement.SEGMENTS,
                Requirement.SEGMENT_TIMESTAMPS,
                Requirement.SPEAKER_LABELS,
            ],
            "enhancements": [],
        },
        "summary": {
            "description": "Executive brief summary derived from highlights",
            "dependencies": ["highlights"],
            "category": "light",
            "determinism_tier": "T0",
            "requirements": [
                Requirement.SEGMENTS,
                Requirement.SEGMENT_TIMESTAMPS,
                Requirement.SPEAKER_LABELS,
            ],
            "enhancements": [],
        },
        "narrative_summary": {
            "description": "Grounded executive narrative from deterministic summary (LLM)",
            "dependencies": ["summary"],
            "category": "medium",
            "determinism_tier": "T2",
            "requirements": [
                Requirement.SEGMENTS,
                Requirement.SEGMENT_TIMESTAMPS,
                Requirement.SPEAKER_LABELS,
            ],
            "enhancements": [],
            "requires_llm": True,
        },
        "llm_summary": {
            "description": "Abstractive transcript summary via local LLM",
            "dependencies": [],
            "category": "medium",
            "determinism_tier": "T2",
            "requirements": [Requirement.SEGMENTS],
            "enhancements": [],
            "requires_llm": True,
        },
        "llm_speaker_summary": {
            "description": "Abstractive per-speaker summaries via local LLM",
            "dependencies": [],
            "category": "medium",
            "determinism_tier": "T2",
            "requirements": [
                Requirement.SEGMENTS,
                Requirement.SPEAKER_LABELS,
            ],
            "enhancements": [],
            "requires_llm": True,
            "min_named_speakers": 1,
        },
        "insights": {
            "description": "Content-first insights layer separated from style markers",
            "dependencies": ["insight_eligibility", "highlights", "topic_modeling"],
            "category": "light",
            "determinism_tier": "T0",
            "requirements": [
                Requirement.SEGMENTS,
                Requirement.SEGMENT_TIMESTAMPS,
                Requirement.SPEAKER_LABELS,
            ],
            "enhancements": [],
        },
    }
