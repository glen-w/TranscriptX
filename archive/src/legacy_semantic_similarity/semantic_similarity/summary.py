"""
Summary generation for repetition analysis.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from transcriptx.core.utils.logger import log_error


def generate_repetition_summary_advanced(
    results: dict[str, Any], method: str, log_tag: str
) -> dict[str, Any]:
    """Generate summary for advanced analyzer results."""
    try:
        speaker_repetitions = results.get("speaker_repetitions", {})
        cross_speaker_repetitions = results.get("cross_speaker_repetitions", [])
        clusters = results.get("clusters", [])

        total_self_repetitions = sum(len(reps) for reps in speaker_repetitions.values())
        total_cross_repetitions = len(cross_speaker_repetitions)
        total_repetitions = total_self_repetitions + total_cross_repetitions

        self_similarities = []
        for reps in speaker_repetitions.values():
            self_similarities.extend([rep.get("similarity", 0) for rep in reps])

        cross_similarities = [
            rep.get("similarity", 0) for rep in cross_speaker_repetitions
        ]

        avg_self_similarity = np.mean(self_similarities) if self_similarities else 0
        avg_cross_similarity = np.mean(cross_similarities) if cross_similarities else 0

        speaker_stats = {}
        for speaker, reps in speaker_repetitions.items():
            speaker_stats[speaker] = {
                "repetitions": len(reps),
                "average_similarity": (
                    np.mean([rep.get("similarity", 0) for rep in reps]) if reps else 0
                ),
            }

        agreement_count = sum(
            1
            for rep in cross_speaker_repetitions
            if rep.get("classification") == "agreement"
        )
        disagreement_count = sum(
            1
            for rep in cross_speaker_repetitions
            if rep.get("classification") == "disagreement"
        )
        neutral_count = sum(
            1
            for rep in cross_speaker_repetitions
            if rep.get("classification") == "neutral"
        )

        return {
            "total_repetitions": total_repetitions,
            "self_repetitions": total_self_repetitions,
            "cross_speaker_repetitions": total_cross_repetitions,
            "clusters_found": len(clusters),
            "average_self_similarity": avg_self_similarity,
            "average_cross_similarity": avg_cross_similarity,
            "speaker_statistics": speaker_stats,
            "agreement_disagreement_breakdown": {
                "agreements": agreement_count,
                "disagreements": disagreement_count,
                "neutral": neutral_count,
            },
            "analysis_method": method,
        }
    except Exception as exc:
        log_error(log_tag, f"Summary generation failed: {exc}", exception=exc)
        return {
            "error": str(exc),
            "total_repetitions": 0,
            "analysis_method": method,
        }


def generate_repetition_summary_basic(results: dict[str, Any]) -> dict[str, Any]:
    """Generate summary statistics for basic analyzer results."""
    self_repetitions = sum(
        len(reps) for reps in results["speaker_repetitions"].values()
    )
    cross_repetitions = len(results["cross_speaker_repetitions"])
    total_repetitions = self_repetitions + cross_repetitions

    agreement_types = Counter()
    for rep in results["cross_speaker_repetitions"]:
        agreement_types[rep.get("agreement_type", "neutral")] += 1

    speaker_frequency = {}
    for speaker, reps in results["speaker_repetitions"].items():
        speaker_frequency[speaker] = len(reps)

    similarities = []
    for reps in results["speaker_repetitions"].values():
        similarities.extend([rep["similarity"] for rep in reps])
    for rep in results["cross_speaker_repetitions"]:
        similarities.append(rep["similarity"])

    avg_similarity = np.mean(similarities) if similarities else 0.0

    return {
        "total_repetitions": total_repetitions,
        "self_repetitions": self_repetitions,
        "cross_speaker_repetitions": cross_repetitions,
        "agreement_breakdown": dict(agreement_types),
        "speaker_repetition_frequency": speaker_frequency,
        "average_similarity": avg_similarity,
        "clusters_found": len(results["repetition_clusters"]),
        "most_repetitive_speaker": (
            max(speaker_frequency.items(), key=lambda x: x[1])[0]
            if speaker_frequency
            else None
        ),
    }
