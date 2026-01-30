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
    NetworkGraphSpec,
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
                "y": [speaker_positions.get(event.speaker_a, 0) for event in type_interactions],
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

    speakers = sorted(set(matrix.keys()) | {s for targets in matrix.values() for s in targets})
    if not speakers:
        return

    index = {speaker: idx for idx, speaker in enumerate(speakers)}
    heatmap = [[0 for _ in speakers] for _ in speakers]
    for speaker_a, targets in matrix.items():
        for speaker_b, interactions in targets.items():
            heatmap[index[speaker_a]][index[speaker_b]] = (
                interactions.get("interruptions", 0) + interactions.get("responses", 0)
            )

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


def create_interaction_network_graph(
    analysis_results: dict[str, Any], output_service: Any, base_name: str
):
    """Create a network graph visualization of speaker interactions."""
    matrix = analysis_results["interaction_matrix"]
    if not matrix or not output_service:
        return

    # Get all speakers
    speakers = sorted(set(matrix.keys()) | {s for targets in matrix.values() for s in targets})
    if not speakers:
        return

    # Calculate node sizes based on total interactions (degree)
    speaker_degrees = {}
    for speaker in speakers:
        total = 0
        # Count outgoing interactions
        for target, interactions in matrix.get(speaker, {}).items():
            total += interactions.get("interruptions", 0) + interactions.get("responses", 0)
        # Count incoming interactions
        for source, targets in matrix.items():
            if speaker in targets:
                total += targets[speaker].get("interruptions", 0) + targets[speaker].get("responses", 0)
        speaker_degrees[speaker] = total

    # Create nodes
    nodes = []
    for speaker in speakers:
        degree = speaker_degrees.get(speaker, 0)
        nodes.append({
            "id": speaker,
            "label": speaker,
            "size": max(20, min(100, degree * 5 + 20)),  # Scale node size
        })

    # Create edges (undirected, combining both directions)
    edges = []
    edge_weights = {}  # Track combined weights for undirected edges
    
    for speaker_a, targets in matrix.items():
        for speaker_b, interactions in targets.items():
            # Combine responses and interruptions
            weight = interactions.get("interruptions", 0) + interactions.get("responses", 0)
            if weight > 0:
                # Use sorted pair as key for undirected edge
                pair = tuple(sorted([speaker_a, speaker_b]))
                if pair not in edge_weights:
                    edge_weights[pair] = 0
                edge_weights[pair] += weight
    
    # Create edges from combined weights
    for (speaker_a, speaker_b), weight in edge_weights.items():
        if weight > 0:
            edges.append({
                "source": speaker_a,
                "target": speaker_b,
                "weight": weight,
                "label": f"res:{int(weight)}",
            })

    if not edges:
        return

    spec = NetworkGraphSpec(
        viz_id="interactions.network_graph.global",
        module="interactions",
        name="network_graph",
        scope="global",
        chart_intent="network_graph",
        title=f"Speaker Interaction Network - {base_name}",
        nodes=nodes,
        edges=edges,
    )
    output_service.save_chart(spec, chart_type="network")


def create_interaction_heatmap(
    analysis_results: dict[str, Any], output_service: Any, base_name: str
):
    """Create heatmaps of speaker interaction matrix."""
    matrix = analysis_results["interaction_matrix"]
    if not matrix or not output_service:
        return

    all_speakers = sorted(set(matrix.keys()) | {s for targets in matrix.values() for s in targets})
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
        for interaction_type in ["interruption_overlap", "interruption_gap", "response"]:
            points = []
            for event, role in speaker_events:
                if event.interaction_type != interaction_type:
                    continue
                other_speaker = event.speaker_b if role == "initiated" else event.speaker_a
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
