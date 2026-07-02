"""Domain-specific module registry definition builders."""

from __future__ import annotations

from typing import Dict, List

from transcriptx.core.domain.module_requirements import Requirement


def build_topics_module_definitions(
    default_requirements: List[Requirement],
) -> Dict[str, Dict]:
    return {
        "semantic_similarity": {
            "description": "Semantic Similarity Analysis (Legacy)",
            "dependencies": [],
            "category": "heavy",
            "determinism_tier": "T1",
            "requirements": default_requirements,
            "enhancements": [],
            "requires_multiple_speakers": True,
            "legacy": True,
        },
        "semantic_similarity_advanced": {
            "description": "Advanced Semantic Similarity with Analysis Integration (Legacy)",
            "dependencies": [],
            "category": "heavy",
            "determinism_tier": "T1",
            "requirements": default_requirements,
            "enhancements": [],
            "requires_multiple_speakers": True,
            "legacy": True,
        },
        "semantic_similarity_v2": {
            "description": "Semantic similarity v2 (batched embeddings, vectorized similarity)",
            "dependencies": [],
            "category": "heavy",
            "determinism_tier": "T1",
            "requirements": default_requirements,
            "enhancements": [],
            "requires_multiple_speakers": True,
        },
        "topic_modeling": {
            "description": "Topic Modeling",
            "dependencies": ["insight_eligibility"],
            "category": "heavy",
            "determinism_tier": "T2",
            "requirements": default_requirements,
            "enhancements": [],
        },
        "wordclouds": {
            "description": "Word Cloud Generation",
            "dependencies": ["insight_eligibility"],
            "category": "light",
            "determinism_tier": "T1",
            "requirements": default_requirements,
            "enhancements": [],
        },
    }
