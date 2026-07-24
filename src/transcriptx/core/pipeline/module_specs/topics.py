"""Domain-specific module registry definition builders."""

from __future__ import annotations

from typing import Dict, List

from transcriptx.core.domain.module_requirements import Requirement


def build_topics_module_definitions(
    default_requirements: List[Requirement],
) -> Dict[str, Dict]:
    return {
        "semantic_similarity": {
            "description": "Semantic similarity (batched embeddings, vectorized similarity)",
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
        "bertopic": {
            "description": (
                "BERTopic topic modeling (optional [bertopic]/[full] stack — "
                "see docs/dev/bertopic_optional_module.md)"
            ),
            "dependencies": ["insight_eligibility"],
            "category": "heavy",
            "determinism_tier": "T2",
            "requirements": default_requirements,
            "enhancements": [],
            "required_extras": ["bertopic"],
            # Embedding + UMAP/HDBSCAN can be slow on large transcripts; hang
            # protection is enforced by the DAG adapter (continues on timeout).
            "timeout_seconds": 3600,
        },
        "wordclouds": {
            "description": "Word Cloud Generation",
            "dependencies": ["insight_eligibility"],
            "optional_dependencies": ["keyphrases"],
            "category": "light",
            "determinism_tier": "T1",
            "requirements": default_requirements,
            "enhancements": [],
        },
    }
