"""Output helpers for interactions analysis."""

from __future__ import annotations

from typing import Any

from transcriptx.core.analysis.interactions.analyzer import SpeakerInteractionAnalyzer
from transcriptx.core.analysis.interactions.events import InteractionEvent
from transcriptx.core.analysis.interactions.visualization import (
    create_combined_timeline,
    create_dominance_analysis,
    create_interaction_heatmap,
    create_interaction_network,
    create_interaction_network_graph,
    create_speaker_timeline_charts,
)
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.output_standards import (
    create_readme_file,
    create_standard_output_structure,
    create_summary_json,
    save_global_data,
    save_speaker_data,
)
from transcriptx.core.output.output_service import create_output_service
from pathlib import Path


def analyze_interactions(
    segments: list[dict],
    base_name: str,
    transcript_dir: str,
    speaker_map: dict[str, str] | None = None,
    transcript_path: str | None = None,
    **kwargs,
) -> dict[str, Any]:
    """
    Analyze speaker interactions in transcript segments and generate comprehensive outputs.

    This is the main function that orchestrates the entire interaction analysis process.
    It creates standardized output structure, detects interactions, analyzes patterns,
    and generates both data files and visualizations.

    Args:
        segments: List of transcript segments
        base_name: Base name for output files
        transcript_dir: Directory to save outputs
        speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility, not used)
        **kwargs: Additional arguments for SpeakerInteractionAnalyzer

    Returns:
        Dictionary containing analysis results
    """
    import warnings

    if speaker_map is not None:
        warnings.warn(
            "speaker_map parameter is deprecated. Speaker identification now uses "
            "speaker_db_id from segments directly.",
            DeprecationWarning,
            stacklevel=2,
        )
    # Create standardized output structure
    output_structure = create_standard_output_structure(transcript_dir, "interactions")
    resolved_path = transcript_path or str(Path(transcript_dir) / f"{base_name}.json")
    output_service = create_output_service(
        resolved_path,
        "interactions",
        output_dir=transcript_dir,
        run_id=Path(transcript_dir).name,
    )

    # Get configuration parameters
    config = get_config()
    overlap_threshold = kwargs.get(
        "overlap_threshold", config.analysis.interaction_overlap_threshold
    )
    min_gap = kwargs.get("min_gap", config.analysis.interaction_min_gap)
    min_segment_length = kwargs.get(
        "min_segment_length", config.analysis.interaction_min_segment_length
    )
    response_threshold = kwargs.get(
        "response_threshold", config.analysis.interaction_response_threshold
    )
    include_responses = kwargs.get(
        "include_responses", config.analysis.interaction_include_responses
    )
    include_overlaps = kwargs.get(
        "include_overlaps", config.analysis.interaction_include_overlaps
    )

    # Initialize analyzer with configuration
    analyzer = SpeakerInteractionAnalyzer(
        overlap_threshold=overlap_threshold,
        min_gap=min_gap,
        min_segment_length=min_segment_length,
        response_threshold=response_threshold,
        include_responses=include_responses,
        include_overlaps=include_overlaps,
    )

    # Detect all interactions in the transcript
    interactions = analyzer.detect_interactions(segments)

    # Analyze interaction patterns and generate statistics (speaker_map not used)
    analysis_results = analyzer.analyze_interactions(interactions, None)

    # Save interaction events data (speaker_map not used, events have display names)
    save_interaction_events(interactions, None, output_structure, base_name)

    # Save speaker summary data
    save_speaker_summary_data(analysis_results, output_structure, base_name)

    # Save interaction matrix data
    save_interaction_matrix_data(analysis_results, output_structure, base_name)

    # Generate visualizations if interactions were detected
    if interactions:
        create_combined_timeline(interactions, None, output_service, base_name)
        create_interaction_network(analysis_results, output_service, base_name)
        create_interaction_network_graph(analysis_results, output_service, base_name)
        create_interaction_heatmap(analysis_results, output_service, base_name)
        create_dominance_analysis(analysis_results, output_service, base_name)
        create_speaker_timeline_charts(interactions, None, output_service, base_name)

        # Create individual speaker charts
        create_speaker_timeline_charts(interactions, None, output_service, base_name)

    # Create comprehensive summary
    create_analysis_summary(analysis_results, output_structure, base_name)

    # Create README file explaining the output structure
    create_readme_file(
        output_structure,
        "interactions",
        base_name,
        "Comprehensive analysis of speaker interactions including interruptions, responses, "
        "and interaction patterns. Provides both global statistics and per-speaker analysis.",
    )

    return analysis_results


def save_interaction_events(
    interactions: list[InteractionEvent],
    speaker_map: dict[str, str] | None = None,
    output_structure=None,
    base_name: str | None = None,
):
    """
    Save interaction events to standardized data files.

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

    # Prepare data for CSV export
    csv_rows = []
    json_data = []

    for event in interactions:
        # Events already contain display names from detect_interactions()
        speaker_a = event.speaker_a
        speaker_b = event.speaker_b

        # Skip interactions involving unnamed speakers
        if not speaker_a or not speaker_b:
            continue

        # Create data row with truncated text for readability
        row = {
            "timestamp": event.timestamp,
            "speaker_a": speaker_a,
            "speaker_b": speaker_b,
            "interaction_type": event.interaction_type,
            "speaker_a_text": (
                event.speaker_a_text[:100] + "..."
                if len(event.speaker_a_text) > 100
                else event.speaker_a_text
            ),
            "speaker_b_text": (
                event.speaker_b_text[:100] + "..."
                if len(event.speaker_b_text) > 100
                else event.speaker_b_text
            ),
            "gap_before": event.gap_before,
            "overlap": event.overlap,
            "speaker_a_start": event.speaker_a_start,
            "speaker_a_end": event.speaker_a_end,
            "speaker_b_start": event.speaker_b_start,
            "speaker_b_end": event.speaker_b_end,
        }

        csv_rows.append(row)
        json_data.append(row)

    # Save to global data directory
    if csv_rows:
        save_global_data(
            csv_rows, output_structure, base_name, "interaction_events", "csv"
        )
        save_global_data(
            {"interactions": json_data},
            output_structure,
            base_name,
            "interaction_events",
            "json",
        )


def save_speaker_summary_data(
    analysis_results: dict[str, Any], output_structure, base_name: str
):
    """
    Save speaker interaction summary data to standardized locations.

    Args:
        analysis_results: Analysis results dictionary
        output_structure: OutputStructure object
        base_name: Base name for files
    """
    # Get all speakers from the analysis
    all_speakers = set(analysis_results["interruption_initiated"].keys()) | set(
        analysis_results["responses_initiated"].keys()
    )

    # Create per-speaker summary data
    for speaker in sorted(all_speakers):
        speaker_data = {
            "speaker": speaker,
            "interruptions_initiated": analysis_results["interruption_initiated"].get(
                speaker, 0
            ),
            "interruptions_received": analysis_results["interruption_received"].get(
                speaker, 0
            ),
            "responses_initiated": analysis_results["responses_initiated"].get(
                speaker, 0
            ),
            "responses_received": analysis_results["responses_received"].get(
                speaker, 0
            ),
            "net_interruption_balance": analysis_results[
                "net_interruption_balance"
            ].get(speaker, 0),
            "net_response_balance": analysis_results["net_response_balance"].get(
                speaker, 0
            ),
            "total_interactions": analysis_results["total_interactions"].get(
                speaker, 0
            ),
            "dominance_score": analysis_results["dominance_scores"].get(speaker, 0),
        }

        # Save per-speaker data
        save_speaker_data(
            speaker_data, output_structure, base_name, speaker, "summary", "json"
        )
        save_speaker_data(
            [speaker_data], output_structure, base_name, speaker, "summary", "csv"
        )

    # Create global summary
    global_summary = []
    for speaker in sorted(all_speakers):
        global_summary.append(
            {
                "speaker": speaker,
                "interruptions_initiated": analysis_results[
                    "interruption_initiated"
                ].get(speaker, 0),
                "interruptions_received": analysis_results["interruption_received"].get(
                    speaker, 0
                ),
                "responses_initiated": analysis_results["responses_initiated"].get(
                    speaker, 0
                ),
                "responses_received": analysis_results["responses_received"].get(
                    speaker, 0
                ),
                "net_interruption_balance": analysis_results[
                    "net_interruption_balance"
                ].get(speaker, 0),
                "net_response_balance": analysis_results["net_response_balance"].get(
                    speaker, 0
                ),
                "total_interactions": analysis_results["total_interactions"].get(
                    speaker, 0
                ),
                "dominance_score": analysis_results["dominance_scores"].get(speaker, 0),
            }
        )

    # Save global summary
    save_global_data(
        global_summary, output_structure, base_name, "speaker_summary", "csv"
    )
    save_global_data(
        analysis_results, output_structure, base_name, "speaker_summary", "json"
    )


def save_interaction_matrix_data(
    analysis_results: dict[str, Any], output_structure, base_name: str
):
    """
    Save interaction matrix data to standardized locations.

    Args:
        analysis_results: Analysis results dictionary
        output_structure: OutputStructure object
        base_name: Base name for files
    """
    matrix = analysis_results["interaction_matrix"]
    if not matrix:
        return

    # Get all unique speakers
    all_speakers = set()
    for speaker_a, targets in matrix.items():
        all_speakers.add(speaker_a)
        all_speakers.update(targets.keys())

    all_speakers = sorted(all_speakers)

    # Create separate matrices for interruptions and responses
    for interaction_type in ["interruptions", "responses"]:
        csv_rows = []
        header = ["speaker_a"] + all_speakers
        csv_rows.append(header)

        for speaker_a in all_speakers:
            row = [speaker_a]
            for speaker_b in all_speakers:
                count = (
                    matrix.get(speaker_a, {})
                    .get(speaker_b, {})
                    .get(interaction_type, 0)
                )
                row.append(count)
            csv_rows.append(row)

        # Save matrix data
        save_global_data(
            csv_rows, output_structure, base_name, f"{interaction_type}_matrix", "csv"
        )


def create_analysis_summary(
    analysis_results: dict[str, Any], output_structure, base_name: str
):
    """
    Create comprehensive analysis summary.

    Args:
        analysis_results: Analysis results dictionary
        output_structure: OutputStructure object
        base_name: Base name for files
    """
    # Create metadata for the analysis
    config = get_config()
    analysis_metadata = {
        "total_interactions": analysis_results["total_interactions_count"],
        "unique_speakers": analysis_results["unique_speakers"],
        "interaction_types": dict(analysis_results["interaction_types"]),
        "analysis_parameters": {
            "overlap_threshold": config.analysis.interaction_overlap_threshold,
            "min_gap": config.analysis.interaction_min_gap,
            "min_segment_length": config.analysis.interaction_min_segment_length,
            "response_threshold": config.analysis.interaction_response_threshold,
            "include_responses": config.analysis.interaction_include_responses,
            "include_overlaps": config.analysis.interaction_include_overlaps,
        },
    }

    # Create summary JSON
    create_summary_json(
        "interactions",
        base_name,
        analysis_results,  # global_data
        analysis_results,  # speaker_data (same for this module)
        analysis_metadata,
        output_structure,
    )
