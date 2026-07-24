"""
Visualization utilities for semantic similarity analysis.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from transcriptx.core.utils.logger import log_error, log_info
from transcriptx.core.viz.specs import BarCategoricalSpec


def create_visualizations_advanced(
    results: dict[str, Any], output_service: Any, base_name: str, log_tag: str
) -> list[str]:
    """Create simplified visualizations for advanced analyzer results."""
    try:
        created_files: list[str] = []

        speaker_stats = results.get("summary", {}).get("speaker_statistics", {})
        if speaker_stats:
            speakers = list(speaker_stats.keys())
            repetition_counts = [
                stats["repetitions"] for stats in speaker_stats.values()
            ]
            avg_similarities = [
                stats["average_similarity"] for stats in speaker_stats.values()
            ]

            rep_spec = BarCategoricalSpec(
                viz_id="semantic_similarity.speaker_repetitions.global",
                module="semantic_similarity",
                name="speaker_repetitions",
                scope="global",
                chart_intent="bar_categorical",
                title="Repetitions by Speaker",
                x_label="Speaker",
                y_label="Number of Repetitions",
                categories=speakers,
                values=repetition_counts,
            )
            created_files.append(output_service.save_chart(rep_spec)["static"])

            sim_spec = BarCategoricalSpec(
                viz_id="semantic_similarity.speaker_similarity.global",
                module="semantic_similarity",
                name="speaker_similarity",
                scope="global",
                chart_intent="bar_categorical",
                title="Average Similarity by Speaker",
                x_label="Speaker",
                y_label="Average Similarity Score",
                categories=speakers,
                values=avg_similarities,
            )
            created_files.append(output_service.save_chart(sim_spec)["static"])

        breakdown = results.get("summary", {}).get(
            "agreement_disagreement_breakdown", {}
        )
        if breakdown:
            categories = list(breakdown.keys())
            counts = list(breakdown.values())
            spec = BarCategoricalSpec(
                viz_id="semantic_similarity.classification.global",
                module="semantic_similarity",
                name="classification",
                scope="global",
                chart_intent="bar_categorical",
                title="Cross-Speaker Repetition Classification",
                x_label="Category",
                y_label="Count",
                categories=categories,
                values=counts,
            )
            created_files.append(output_service.save_chart(spec)["static"])

        all_similarities: list[float] = []
        for reps in results.get("speaker_repetitions", {}).values():
            all_similarities.extend([rep.get("similarity", 0) for rep in reps])
        all_similarities.extend(
            [
                rep.get("similarity", 0)
                for rep in results.get("cross_speaker_repetitions", [])
            ]
        )
        if all_similarities:
            counts, bin_edges = np.histogram(all_similarities, bins=20)
            categories = [
                f"{bin_edges[i]:.2f}-{bin_edges[i + 1]:.2f}" for i in range(len(counts))
            ]
            spec = BarCategoricalSpec(
                viz_id="semantic_similarity.similarity_distribution.global",
                module="semantic_similarity",
                name="similarity_distribution",
                scope="global",
                chart_intent="bar_categorical",
                title="Distribution of Similarity Scores",
                x_label="Similarity Score",
                y_label="Frequency",
                categories=categories,
                values=counts.tolist(),
            )
            created_files.append(output_service.save_chart(spec)["static"])

        log_info(log_tag, f"Created {len(created_files)} visualizations")
        return [str(p) for p in created_files if p]
    except Exception as exc:
        log_error(log_tag, f"Visualization creation failed: {exc}", exception=exc)
        return []


def create_visualizations_basic(
    results: dict[str, Any], output_service: Any, base_name: str, log_tag: str
) -> list[str]:
    """Create simplified visualizations for basic analyzer results."""
    chart_paths: list[str] = []
    summary = results.get("summary", {})

    try:
        speaker_frequency = summary.get("speaker_repetition_frequency", {})
        if speaker_frequency:
            actual_speakers = set(results.get("speaker_repetitions", {}).keys())
            actual_speakers = {s for s in actual_speakers if s and s != "Unknown"}
            filtered = {
                s: speaker_frequency[s]
                for s in speaker_frequency
                if s in actual_speakers
            }
            speakers = sorted(filtered.keys())
            frequencies = [filtered[s] for s in speakers]
            if speakers:
                spec = BarCategoricalSpec(
                    viz_id="semantic_similarity.speaker_repetition_frequency.global",
                    module="semantic_similarity",
                    name="speaker_repetition_frequency",
                    scope="global",
                    chart_intent="bar_categorical",
                    title=f"Speaker Repetition Frequency - {base_name}",
                    x_label="Speaker",
                    y_label="Number of Repetitions",
                    categories=speakers,
                    values=frequencies,
                )
                chart_paths.append(output_service.save_chart(spec)["static"])

        agreement_breakdown = summary.get("agreement_breakdown", {})
        if agreement_breakdown:
            agreement_types = list(agreement_breakdown.keys())
            counts = list(agreement_breakdown.values())
            spec = BarCategoricalSpec(
                viz_id="semantic_similarity.agreement_disagreement_breakdown.global",
                module="semantic_similarity",
                name="agreement_disagreement_breakdown",
                scope="global",
                chart_intent="bar_categorical",
                title=f"Cross-Speaker Interaction Types - {base_name}",
                x_label="Interaction Type",
                y_label="Count",
                categories=agreement_types,
                values=counts,
            )
            chart_paths.append(output_service.save_chart(spec)["static"])

        similarities: list[float] = []
        for reps in results["speaker_repetitions"].values():
            similarities.extend([rep["similarity"] for rep in reps])
        for rep in results["cross_speaker_repetitions"]:
            similarities.append(rep["similarity"])

        if similarities:
            counts, bin_edges = np.histogram(similarities, bins=20)
            categories = [
                f"{bin_edges[i]:.2f}-{bin_edges[i + 1]:.2f}" for i in range(len(counts))
            ]
            spec = BarCategoricalSpec(
                viz_id="semantic_similarity.similarity_distribution.global",
                module="semantic_similarity",
                name="similarity_distribution",
                scope="global",
                chart_intent="bar_categorical",
                title=f"Semantic Similarity Distribution - {base_name}",
                x_label="Similarity Score",
                y_label="Frequency",
                categories=categories,
                values=counts.tolist(),
            )
            chart_paths.append(output_service.save_chart(spec)["static"])

    except Exception as exc:
        log_error(log_tag, f"Failed to create visualizations: {exc}")

    return [str(p) for p in chart_paths if p]
