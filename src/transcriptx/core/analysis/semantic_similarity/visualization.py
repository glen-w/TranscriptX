"""Visualization utilities for semantic_similarity outputs."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

import numpy as np

from transcriptx.core.utils.logger import log_error, log_info
from transcriptx.core.viz.specs import BarCategoricalSpec

MODULE_ID = "semantic_similarity"


def _all_repetitions(results: dict[str, Any]) -> list[dict[str, Any]]:
    repetitions: list[dict[str, Any]] = []
    speaker_repetitions = results.get("speaker_repetitions", {})
    if isinstance(speaker_repetitions, dict):
        for reps in speaker_repetitions.values():
            if isinstance(reps, list):
                repetitions.extend(r for r in reps if isinstance(r, dict))

    cross_speaker = results.get("cross_speaker_repetitions", [])
    if isinstance(cross_speaker, list):
        repetitions.extend(r for r in cross_speaker if isinstance(r, dict))
    return repetitions


def _similarity_values(repetitions: Iterable[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for rep in repetitions:
        try:
            values.append(float(rep.get("similarity", 0.0)))
        except (TypeError, ValueError):
            continue
    return values


def _speaker_from_segment(rep: dict[str, Any], segment_key: str) -> str | None:
    segment = rep.get(segment_key)
    if not isinstance(segment, dict):
        return None
    speaker = segment.get("speaker")
    return str(speaker) if speaker else None


def _record_saved_path(saved: dict[str, Any], chart_paths: list[str]) -> None:
    static_path = saved.get("static")
    if static_path:
        chart_paths.append(str(static_path))


def _bar_spec(
    *,
    viz_id: str,
    name: str,
    title: str,
    x_label: str,
    y_label: str,
    categories: list[str],
    values: list[float],
) -> BarCategoricalSpec:
    return BarCategoricalSpec(
        viz_id=viz_id,
        module=MODULE_ID,
        name=name,
        scope="global",
        chart_intent="bar_categorical",
        title=title,
        x_label=x_label,
        y_label=y_label,
        categories=categories,
        values=values,
    )


def create_visualizations(
    results: dict[str, Any], output_service: Any, base_name: str, log_tag: str
) -> list[str]:
    """Create legacy-equivalent charts for semantic_similarity results."""
    chart_paths: list[str] = []

    try:
        speaker_repetitions = results.get("speaker_repetitions", {})
        if isinstance(speaker_repetitions, dict):
            speaker_counts = {
                str(speaker): len(reps)
                for speaker, reps in speaker_repetitions.items()
                if speaker and isinstance(reps, list) and len(reps) > 0
            }
        else:
            speaker_counts = {}

        if speaker_counts:
            speakers = sorted(speaker_counts)
            counts = [float(speaker_counts[speaker]) for speaker in speakers]
            for name, viz_id, title in (
                (
                    "speaker_repetition_frequency",
                    "semantic_similarity.speaker_repetition_frequency.global",
                    f"Speaker Repetition Frequency - {base_name}",
                ),
                (
                    "speaker_repetitions",
                    "semantic_similarity.speaker_repetitions.global",
                    "Repetitions by Speaker",
                ),
            ):
                _record_saved_path(
                    output_service.save_chart(
                        _bar_spec(
                            viz_id=viz_id,
                            name=name,
                            title=title,
                            x_label="Speaker",
                            y_label="Number of Repetitions",
                            categories=speakers,
                            values=counts,
                        )
                    ),
                    chart_paths,
                )

        all_reps = _all_repetitions(results)
        speaker_similarity: dict[str, list[float]] = defaultdict(list)
        for rep in all_reps:
            try:
                similarity = float(rep.get("similarity", 0.0))
            except (TypeError, ValueError):
                continue
            for segment_key in ("segment1", "segment2"):
                speaker = _speaker_from_segment(rep, segment_key)
                if speaker:
                    speaker_similarity[speaker].append(similarity)

        if speaker_similarity:
            speakers = sorted(speaker_similarity)
            avg_similarity = [
                float(np.mean(speaker_similarity[speaker])) for speaker in speakers
            ]
            _record_saved_path(
                output_service.save_chart(
                    _bar_spec(
                        viz_id="semantic_similarity.speaker_similarity.global",
                        name="speaker_similarity",
                        title="Average Similarity by Speaker",
                        x_label="Speaker",
                        y_label="Average Similarity Score",
                        categories=speakers,
                        values=avg_similarity,
                    )
                ),
                chart_paths,
            )

        cross_speaker = results.get("cross_speaker_repetitions", [])
        agreement_counts: Counter[str] = Counter()
        if isinstance(cross_speaker, list):
            for rep in cross_speaker:
                if not isinstance(rep, dict):
                    continue
                label = rep.get("agreement_type") or rep.get("type") or "cross"
                agreement_counts[str(label)] += 1

        if agreement_counts:
            categories = sorted(agreement_counts)
            values = [float(agreement_counts[c]) for c in categories]
            _record_saved_path(
                output_service.save_chart(
                    _bar_spec(
                        viz_id=(
                            "semantic_similarity."
                            "agreement_disagreement_breakdown.global"
                        ),
                        name="agreement_disagreement_breakdown",
                        title=f"Cross-Speaker Interaction Types - {base_name}",
                        x_label="Interaction Type",
                        y_label="Count",
                        categories=categories,
                        values=values,
                    )
                ),
                chart_paths,
            )

        classification_counts: Counter[str] = Counter()
        if speaker_counts:
            classification_counts["self_repetition"] = sum(speaker_counts.values())
        classification_counts.update(agreement_counts)
        if classification_counts:
            categories = sorted(classification_counts)
            values = [float(classification_counts[c]) for c in categories]
            _record_saved_path(
                output_service.save_chart(
                    _bar_spec(
                        viz_id="semantic_similarity.classification.global",
                        name="classification",
                        title="Cross-Speaker Repetition Classification",
                        x_label="Category",
                        y_label="Count",
                        categories=categories,
                        values=values,
                    )
                ),
                chart_paths,
            )

        similarities = _similarity_values(all_reps)
        if similarities:
            counts, bin_edges = np.histogram(similarities, bins=20)
            categories = [
                f"{bin_edges[i]:.2f}-{bin_edges[i + 1]:.2f}" for i in range(len(counts))
            ]
            _record_saved_path(
                output_service.save_chart(
                    _bar_spec(
                        viz_id="semantic_similarity.similarity_distribution.global",
                        name="similarity_distribution",
                        title=f"Semantic Similarity Distribution - {base_name}",
                        x_label="Similarity Score",
                        y_label="Frequency",
                        categories=categories,
                        values=[float(v) for v in counts.tolist()],
                    )
                ),
                chart_paths,
            )

        log_info(log_tag, f"Created {len(chart_paths)} v2 visualizations")
        return chart_paths
    except Exception as exc:
        log_error(log_tag, f"Visualization creation failed: {exc}", exception=exc)
        return []
