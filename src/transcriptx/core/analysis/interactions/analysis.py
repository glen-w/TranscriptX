"""Speaker interactions analysis module."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.interactions.analyzer import SpeakerInteractionAnalyzer
from transcriptx.core.analysis.interactions.output import create_analysis_summary
from transcriptx.core.analysis.interactions.visualization import (
    create_dominance_analysis,
    create_interaction_heatmap,
    create_interaction_network,
    create_interaction_network_graph,
)


class InteractionsAnalysis(AnalysisModule):
    """
    Speaker interactions analysis module.

    This module analyzes speaker interactions including interruptions,
    responses, and interaction patterns.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the interactions analysis module."""
        super().__init__(config)
        self.module_name = "interactions"

        # Initialize analyzer with config
        self.analyzer = SpeakerInteractionAnalyzer(
            overlap_threshold=self.config.get("overlap_threshold", 0.5),
            min_gap=self.config.get("min_gap", 0.1),
            min_segment_length=self.config.get("min_segment_length", 0.5),
            response_threshold=self.config.get("response_threshold", 2.0),
            include_responses=self.config.get("include_responses", True),
            include_overlaps=self.config.get("include_overlaps", True),
        )

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Perform interactions analysis on transcript segments (pure logic, no I/O).

        Args:
            segments: List of transcript segments
            speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility)

        Returns:
            Dictionary containing interactions analysis results
        """
        # Detect interactions
        interactions = self.analyzer.detect_interactions(segments)

        # Analyze interaction patterns
        analysis_results = self.analyzer.analyze_interactions(
            interactions, speaker_map or {}
        )

        # Convert InteractionEvent objects to dictionaries for JSON serialization
        interactions_dict = [asdict(event) for event in interactions]

        # Add interactions to results
        analysis_results["interactions"] = interactions_dict
        # Backward-compatible keys for tests/legacy consumers
        analysis_results["turns"] = interactions_dict
        analysis_results["turn_taking"] = {
            "responses_initiated": analysis_results.get("responses_initiated", {}),
            "responses_received": analysis_results.get("responses_received", {}),
            "interruptions_initiated": analysis_results.get("interruption_initiated", {}),
            "interruptions_received": analysis_results.get("interruption_received", {}),
            "total_interactions": analysis_results.get("total_interactions_count", 0),
        }
        analysis_results["summary"] = {
            "total_interactions": analysis_results.get("total_interactions_count", 0),
            "unique_speakers": analysis_results.get("unique_speakers", 0),
        }

        return analysis_results

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """
        Save results using OutputService (new interface).

        Args:
            results: Analysis results dictionary
            output_service: OutputService instance
        """
        interactions = results.get("interactions", [])
        base_name = output_service.base_name
        output_structure = output_service.get_output_structure()

        # Save interaction data
        # Interactions are now dictionaries (converted from InteractionEvent objects in analyze())
        interaction_data = [
            {
                "timestamp": event["timestamp"],
                "speaker_a": event["speaker_a"],
                "speaker_b": event["speaker_b"],
                "interaction_type": event["interaction_type"],
                "gap_before": event["gap_before"],
                "overlap": event["overlap"],
            }
            for event in interactions
        ]

        output_service.save_data(interaction_data, "interactions", format_type="json")
        output_service.save_data(interaction_data, "interactions", format_type="csv")

        # Ensure charts/global directory exists (required for validation)
        output_structure.global_charts_dir.mkdir(parents=True, exist_ok=True)

        # Generate visualizations using existing functions
        if interactions:
            self._create_interaction_network(results, output_service, base_name)
            self._create_interaction_charts(results, output_service, base_name)

        # Create comprehensive summary
        self._create_analysis_summary(results, output_structure, base_name, output_service)

    def _create_interaction_network(
        self,
        analysis_results: Dict[str, Any],
        output_service: "OutputService",
        base_name: str,
    ) -> None:
        """Create interaction network visualization."""
        create_interaction_network(analysis_results, output_service, base_name)
        create_interaction_network_graph(analysis_results, output_service, base_name)

    def _create_interaction_charts(
        self,
        analysis_results: Dict[str, Any],
        output_service: "OutputService",
        base_name: str,
    ) -> None:
        """Create interaction charts."""
        # Create additional interaction visualizations
        create_interaction_heatmap(analysis_results, output_service, base_name)
        create_dominance_analysis(analysis_results, output_service, base_name)

    def _create_analysis_summary(
        self,
        analysis_results: Dict[str, Any],
        output_structure,
        base_name: str,
        output_service: "OutputService",
    ) -> None:
        """Create analysis summary."""
        create_analysis_summary(analysis_results, output_structure, base_name)

        # Also save summary using OutputService
        global_stats = {
            "total_interactions": analysis_results.get("total_interactions_count", 0),
            "unique_speakers": analysis_results.get("unique_speakers", 0),
        }
        speaker_stats = {
            speaker: {
                "interruptions_initiated": analysis_results.get(
                    "interruption_initiated", {}
                ).get(speaker, 0),
                "interruptions_received": analysis_results.get(
                    "interruption_received", {}
                ).get(speaker, 0),
                "responses_initiated": analysis_results.get(
                    "responses_initiated", {}
                ).get(speaker, 0),
                "responses_received": analysis_results.get(
                    "responses_received", {}
                ).get(speaker, 0),
                "dominance_score": analysis_results.get("dominance_scores", {}).get(
                    speaker, 0
                ),
            }
            for speaker in analysis_results.get("total_interactions", {}).keys()
        }
        output_service.save_summary(global_stats, speaker_stats, analysis_metadata={})
