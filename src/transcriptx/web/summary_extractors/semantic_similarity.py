"""
Summary extractor for semantic similarity analysis.
"""

from typing import Dict, Any
from . import register_extractor


def extract_semantic_similarity_summary(
    data: Dict[str, Any], summary: Dict[str, Any]
) -> None:
    """Extract summary from semantic similarity analysis data."""
    speaker_repetitions = data.get("speaker_repetitions")
    cross_speaker_repetitions = data.get("cross_speaker_repetitions")
    if isinstance(speaker_repetitions, dict) or isinstance(
        cross_speaker_repetitions, list
    ):
        self_count = sum(
            len(reps)
            for reps in (speaker_repetitions or {}).values()
            if isinstance(reps, list)
        )
        cross_count = (
            len(cross_speaker_repetitions)
            if isinstance(cross_speaker_repetitions, list)
            else 0
        )
        similarities = []
        for reps in (speaker_repetitions or {}).values():
            if isinstance(reps, list):
                similarities.extend(
                    rep.get("similarity", 0) for rep in reps if isinstance(rep, dict)
                )
        if isinstance(cross_speaker_repetitions, list):
            similarities.extend(
                rep.get("similarity", 0)
                for rep in cross_speaker_repetitions
                if isinstance(rep, dict)
            )

        summary["key_metrics"]["Self Repetitions"] = self_count
        summary["key_metrics"]["Cross-Speaker Repetitions"] = cross_count
        summary["key_metrics"]["Total Repetitions"] = data.get(
            "total_repetitions", self_count + cross_count
        )
        if similarities:
            avg_similarity = sum(float(s or 0) for s in similarities) / len(
                similarities
            )
            summary["key_metrics"]["Average Similarity"] = f"{avg_similarity:.2f}"
        return

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
register_extractor("semantic_similarity_v2", extract_semantic_similarity_summary)
