"""Visualization helpers for interactions analysis."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from transcriptx.core.analysis.interactions.events import InteractionEvent
from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.core.viz.specs import (
    BarCategoricalSpec,
    HeatmapMatrixSpec,
    LineTimeSeriesSpec,
)


def create_combined_timeline(
    interactions: list[InteractionEvent],
    speaker_map: dict[str, str] | None = None,
    output_service=None,
    base_name: str | None = None,
):
    """
    Create combined timeline plot of all interactions.

    Args:
        interactions: List of InteractionEvent objects
        speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility, not used)
        output_service: OutputService instance
        base_name: Base name for files
    """
    import warnings

    if speaker_map is not None:
        warnings.warn(
            "speaker_map parameter is deprecated. Speaker names come from InteractionEvent objects.",
            DeprecationWarning,
            stacklevel=2,
        )

    if not interactions or not output_service:
        return

    # Sort interactions by timestamp
    sorted_interactions = sorted(interactions, key=lambda x: x.timestamp)

    # Collect all unique speakers from interactions (events already contain display names)
    unique_speakers = sorted(
        {
            event.speaker_a
            for event in interactions
            if event.speaker_a and is_named_speaker(event.speaker_a)
        }
        | {
            event.speaker_b
            for event in interactions
            if event.speaker_b and is_named_speaker(event.speaker_b)
        }
    )
    speaker_positions = {speaker: idx for idx, speaker in enumerate(unique_speakers)}

    series = []
    for interaction_type in ["interruption_overlap", "interruption_gap", "response"]:
        type_interactions = [
            e for e in sorted_interactions if e.interaction_type == interaction_type
        ]
        if not type_interactions:
            continue
        series.append(
            {
                "name": interaction_type.replace("_", " ").title(),
                "x": [event.timestamp / 60.0 for event in type_interactions],
                "y": [
                    speaker_positions.get(event.speaker_a, 0)
                    for event in type_interactions
                ],
            }
        )

    if series:
        spec = LineTimeSeriesSpec(
            viz_id="interactions.timeline.global",
            module="interactions",
            name="timeline",
            scope="global",
            chart_intent="line_timeseries",
            title=f"Speaker Interaction Timeline - {base_name}",
            x_label="Time (minutes)",
            y_label="Speaker (index)",
            markers=True,
            series=series,
        )
        output_service.save_chart(spec, chart_type="timeline")


def create_interaction_network(
    analysis_results: dict[str, Any], output_service: Any, base_name: str
):
    """Create a simplified interaction network heatmap."""
    matrix = analysis_results["interaction_matrix"]
    if not matrix or not output_service:
        return

    speakers = sorted(
        set(matrix.keys()) | {s for targets in matrix.values() for s in targets}
    )
    if not speakers:
        return

    index = {speaker: idx for idx, speaker in enumerate(speakers)}
    heatmap = [[0 for _ in speakers] for _ in speakers]
    for speaker_a, targets in matrix.items():
        for speaker_b, interactions in targets.items():
            heatmap[index[speaker_a]][index[speaker_b]] = interactions.get(
                "interruptions", 0
            ) + interactions.get("responses", 0)

    spec = HeatmapMatrixSpec(
        viz_id="interactions.network.global",
        module="interactions",
        name="network",
        scope="global",
        chart_intent="heatmap_matrix",
        title=f"Speaker Interaction Network - {base_name}",
        x_label="To Speaker",
        y_label="From Speaker",
        z=heatmap,
        x_labels=speakers,
        y_labels=speakers,
    )
    output_service.save_chart(spec, chart_type="network")


def create_interaction_heatmap(
    analysis_results: dict[str, Any], output_service: Any, base_name: str
):
    """Create heatmaps of speaker interaction matrix."""
    matrix = analysis_results["interaction_matrix"]
    if not matrix or not output_service:
        return

    all_speakers = sorted(
        set(matrix.keys()) | {s for targets in matrix.values() for s in targets}
    )
    if not all_speakers:
        return

    interruption_data = []
    response_data = []
    for speaker_a in all_speakers:
        interruption_row = []
        response_row = []
        for speaker_b in all_speakers:
            interruption_row.append(
                matrix.get(speaker_a, {}).get(speaker_b, {}).get("interruptions", 0)
            )
            response_row.append(
                matrix.get(speaker_a, {}).get(speaker_b, {}).get("responses", 0)
            )
        interruption_data.append(interruption_row)
        response_data.append(response_row)

    interruption_total = sum(sum(row) for row in interruption_data)
    response_total = sum(sum(row) for row in response_data)
    interruption_note = (
        "None detected in this transcript." if interruption_total == 0 else None
    )
    response_note = "None detected in this transcript." if response_total == 0 else None

    interruption_spec = HeatmapMatrixSpec(
        viz_id="interactions.heatmap_interruptions.global",
        module="interactions",
        name="heatmap_interruptions",
        scope="global",
        chart_intent="heatmap_matrix",
        title=f"Interruption Matrix - {base_name}",
        x_label="Interrupted Speaker",
        y_label="Interrupting Speaker",
        z=interruption_data,
        x_labels=all_speakers,
        y_labels=all_speakers,
        notes=interruption_note,
    )
    output_service.save_chart(interruption_spec, chart_type="heatmap")

    response_spec = HeatmapMatrixSpec(
        viz_id="interactions.heatmap_responses.global",
        module="interactions",
        name="heatmap_responses",
        scope="global",
        chart_intent="heatmap_matrix",
        title=f"Response Matrix - {base_name}",
        x_label="Responded To Speaker",
        y_label="Responding Speaker",
        z=response_data,
        x_labels=all_speakers,
        y_labels=all_speakers,
        notes=response_note,
    )
    output_service.save_chart(response_spec, chart_type="heatmap")


def create_dominance_analysis(
    analysis_results: dict[str, Any], output_service: Any, base_name: str
):
    """Create dominance analysis visualization."""
    dominance_scores = analysis_results["dominance_scores"]
    if not dominance_scores or not output_service:
        return

    speakers = list(dominance_scores.keys())
    scores = list(dominance_scores.values())
    spec = BarCategoricalSpec(
        viz_id="interactions.dominance.global",
        module="interactions",
        name="dominance",
        scope="global",
        chart_intent="bar_categorical",
        title=f"Speaker Dominance Analysis - {base_name}",
        x_label="Speaker",
        y_label="Dominance Score",
        categories=speakers,
        values=scores,
    )
    output_service.save_chart(spec, chart_type="dominance")


def create_equity_floor_chart(
    analysis_results: dict[str, Any], output_service: Any, base_name: str
) -> None:
    """Floor-share bars when total valid duration > 0 (even if equity index abstains)."""
    if not output_service:
        return
    equity = analysis_results.get("equity") or {}
    floor_share = equity.get("floor_share") or {}
    if not floor_share:
        return
    # Defined shares imply total valid duration > 0
    speakers = sorted(floor_share.keys())
    values = [float(floor_share[s]) for s in speakers]
    spec = BarCategoricalSpec(
        viz_id="interactions.equity.floor.global",
        module="interactions",
        name="equity_floor",
        scope="global",
        chart_intent="bar_categorical",
        title=f"Speaking Floor Share - {base_name}",
        x_label="Speaker",
        y_label="Floor share",
        categories=speakers,
        values=values,
        notes="Claimed speaking-time shares (raw segment lengths; overlaps not collapsed).",
    )
    output_service.save_chart(spec, chart_type="equity_floor")


def create_equity_summary_chart(
    analysis_results: dict[str, Any], output_service: Any, base_name: str
) -> None:
    """
    Session equity indices: render available metrics independently.

    interruption_balance_index is presentation-derived (1 - asymmetry), not persisted.
    """
    if not output_service:
        return
    from transcriptx.core.analysis.interactions.roles import interruption_balance_index

    equity = analysis_results.get("equity") or {}
    categories: list[str] = []
    values: list[float] = []

    # Deterministic metric order
    floor_idx = equity.get("floor_equity_index")
    if floor_idx is not None:
        categories.append("Floor equity")
        values.append(float(floor_idx))

    asym = equity.get("interruption_asymmetry_index")
    if asym is not None:
        categories.append("Interruption inequity")
        values.append(float(asym))
        balance = interruption_balance_index(float(asym))
        if balance is not None:
            categories.append("Interruption balance")
            values.append(float(balance))

    latency_fair = equity.get("response_latency_fairness_index")
    if latency_fair is not None:
        categories.append("Response latency fairness")
        values.append(float(latency_fair))

    if not categories:
        return

    spec = BarCategoricalSpec(
        viz_id="interactions.equity.summary.global",
        module="interactions",
        name="equity_summary",
        scope="global",
        chart_intent="bar_categorical",
        title=f"Turn-taking Equity Summary - {base_name}",
        x_label="Metric",
        y_label="Index (0–1)",
        categories=categories,
        values=values,
        notes=(
            "Floor equity and latency fairness: higher is fairer. "
            "Interruption inequity: higher is more asymmetric. "
            "Interruption balance = 1 − inequity (presentation only)."
        ),
    )
    output_service.save_chart(spec, chart_type="equity_summary")


def create_speaker_timeline_charts(
    interactions: list[InteractionEvent],
    speaker_map: dict[str, str] | None = None,
    output_service=None,
    base_name: str | None = None,
):
    """
    Create individual timeline charts for each speaker showing their interactions.

    Args:
        interactions: List of InteractionEvent objects
        speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility, not used)
        output_structure: OutputStructure object
        base_name: Base name for files
    """
    import warnings

    if speaker_map is not None:
        warnings.warn(
            "speaker_map parameter is deprecated. Speaker names come from InteractionEvent objects.",
            DeprecationWarning,
            stacklevel=2,
        )

    # Group interactions by speaker
    speaker_interactions = defaultdict(list)

    for event in interactions:
        # Events already contain display names from detect_interactions()
        speaker_a = event.speaker_a
        speaker_b = event.speaker_b

        # Skip interactions involving unnamed speakers
        if (
            not speaker_a
            or not speaker_b
            or not is_named_speaker(speaker_a)
            or not is_named_speaker(speaker_b)
        ):
            continue

        # Add to both speakers' interaction lists
        speaker_interactions[speaker_a].append((event, "initiated"))
        speaker_interactions[speaker_b].append((event, "received"))

    if not output_service:
        return

    # Create individual charts for each speaker
    for speaker, speaker_events in speaker_interactions.items():
        if not speaker_events or not speaker:
            continue

        # Sort events by timestamp
        speaker_events.sort(key=lambda x: x[0].timestamp)

        other_speakers = sorted(
            {
                (event.speaker_b if role == "initiated" else event.speaker_a)
                for event, role in speaker_events
                if (event.speaker_b if role == "initiated" else event.speaker_a)
            }
        )
        other_map = {name: idx for idx, name in enumerate(other_speakers)}

        series = []
        for interaction_type in [
            "interruption_overlap",
            "interruption_gap",
            "response",
        ]:
            points = []
            for event, role in speaker_events:
                if event.interaction_type != interaction_type:
                    continue
                other_speaker = (
                    event.speaker_b if role == "initiated" else event.speaker_a
                )
                points.append((event.timestamp / 60.0, other_map.get(other_speaker, 0)))
            if points:
                series.append(
                    {
                        "name": interaction_type.replace("_", " ").title(),
                        "x": [pt[0] for pt in points],
                        "y": [pt[1] for pt in points],
                    }
                )

        if series:
            spec = LineTimeSeriesSpec(
                viz_id="interactions.timeline.speaker",
                module="interactions",
                name="timeline",
                scope="speaker",
                speaker=speaker,
                chart_intent="line_timeseries",
                title=f"{speaker}'s Interaction Timeline - {base_name}",
                x_label="Time (minutes)",
                y_label="Other Speaker (index)",
                markers=True,
                series=series,
            )
            output_service.save_chart(spec, chart_type="timeline")
