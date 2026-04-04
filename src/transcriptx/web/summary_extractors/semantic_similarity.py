"""
Summary extractor for semantic similarity analysis.
"""

from typing import Dict, Any
from . import register_extractor


def extract_semantic_similarity_summary(
    data: Dict[str, Any], summary: Dict[str, Any]
) -> None:
    """Extract summary from semantic similarity analysis data."""
    similarities = data.get("similarities", [])
    if similarities:
        summary["key_metrics"]["Similarity Pairs"] = len(similarities)
        if similarities:
            avg_similarity = sum(s.get("similarity", 0) for s in similarities) / len(
                similarities
            )
            summary["key_metrics"]["Average Similarity"] = f"{avg_similarity:.2f}"


# Register for both semantic_similarity and semantic_similarity_advanced
register_extractor("semantic_similarity", extract_semantic_similarity_summary)
register_extractor("semantic_similarity_advanced", extract_semantic_similarity_summary)
