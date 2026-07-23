"""Speaker interactions analysis module."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.interactions.analyzer import SpeakerInteractionAnalyzer
from transcriptx.core.analysis.interactions.equity import compute_equity
from transcriptx.core.analysis.interactions.events import InteractionEvent
from transcriptx.core.analysis.interactions.output import create_analysis_summary
from transcriptx.core.analysis.interactions.roles import INTERACTIONS_SEMANTICS_VERSION
from transcriptx.core.analysis.interactions.serialize import (
    serialize_equity,
    serialize_interactions_summary,
)
from transcriptx.core.analysis.interactions.graph_export import commit_interaction_graph
from transcriptx.core.analysis.interactions.visualization import (
    create_combined_timeline,
    create_dominance_analysis,
    create_equity_floor_chart,
    create_equity_summary_chart,
    create_interaction_heatmap,
    create_interaction_network,
    create_speaker_timeline_charts,
)
from transcriptx.core.utils.segment_duration import compute_eligible_speaker_durations


class InteractionsAnalysis(AnalysisModule):
    """
    Speaker interactions analysis module.

    This module analyzes speaker interactions including interruptions,
    responses, interaction patterns, and turn-taking equity.
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
        interactions = self.analyzer.detect_interactions(segments)
        analysis_results = self.analyzer.analyze_interactions(
            interactions, speaker_map or {}
        )

        duration_result = compute_eligible_speaker_durations(segments)
        equity = compute_equity(
            duration_result=duration_result,
            interruption_initiated=analysis_results.get("interruption_initiated", {}),
            interruption_received=analysis_results.get("interruption_received", {}),
            interactions=interactions,
        )
        analysis_results["equity"] = serialize_equity(equity)
        analysis_results["speaker_key_map"] = dict(
            getattr(duration_result, "speaker_key_map", {}) or {}
        )
        analysis_results["semantics_version"] = analysis_results.get(
            "semantics_version", INTERACTIONS_SEMANTICS_VERSION
        )

        interactions_dict = [asdict(event) for event in interactions]
        analysis_results["interactions"] = interactions_dict
        analysis_results["turns"] = interactions_dict
        analysis_results["turn_taking"] = {
            "responses_initiated": analysis_results.get("responses_initiated", {}),
            "responses_received": analysis_results.get("responses_received", {}),
            "interruptions_initiated": analysis_results.get(
                "interruption_initiated", {}
            ),
            "interruptions_received": analysis_results.get("interruption_received", {}),
            "total_interactions": analysis_results.get("total_interactions_count", 0),
        }
        analysis_results["summary"] = {
            "total_interactions": analysis_results.get("total_interactions_count", 0),
            "unique_speakers": analysis_results.get("unique_speakers", 0),
            "semantics_version": analysis_results["semantics_version"],
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

        output_structure.global_charts_dir.mkdir(parents=True, exist_ok=True)

        # B13 graph artifacts: always run so empty reruns clear stale files
        events_for_graph = [
            InteractionEvent(**event) if isinstance(event, dict) else event
            for event in interactions
        ]
        commit_interaction_graph(
            interactions=events_for_graph,
            analysis_results=results,
            output_service=output_service,
        )

        if interactions:
            self._create_interaction_network(results, output_service, base_name)
            self._create_interaction_charts(results, output_service, base_name)

        # Equity charts may render even when event list is empty (floor shares)
        create_equity_floor_chart(results, output_service, base_name)
        create_equity_summary_chart(results, output_service, base_name)

        self._create_analysis_summary(
            results, output_structure, base_name, output_service
        )

    def _create_interaction_network(
        self,
        analysis_results: Dict[str, Any],
        output_service: "OutputService",
        base_name: str,
    ) -> None:
        """Create interaction network heatmap (graph chart is via commit_interaction_graph)."""
        create_interaction_network(analysis_results, output_service, base_name)

    def _create_interaction_charts(
        self,
        analysis_results: Dict[str, Any],
        output_service: "OutputService",
        base_name: str,
    ) -> None:
        """Create interaction charts."""
        events = [
            InteractionEvent(**event) if isinstance(event, dict) else event
            for event in analysis_results.get("interactions", [])
        ]
        create_combined_timeline(events, None, output_service, base_name)
        create_interaction_heatmap(analysis_results, output_service, base_name)
        create_dominance_analysis(analysis_results, output_service, base_name)
        create_speaker_timeline_charts(events, None, output_service, base_name)

    def _create_analysis_summary(
        self,
        analysis_results: Dict[str, Any],
        output_structure,
        base_name: str,
        output_service: "OutputService",
    ) -> None:
        """Create analysis summary."""
        create_analysis_summary(analysis_results, output_structure, base_name)

        serialized = serialize_interactions_summary(analysis_results)
        output_service.save_summary(
            serialized["global"],
            serialized["speakers"],
            analysis_metadata={
                "semantics_version": serialized["semantics_version"],
            },
        )
