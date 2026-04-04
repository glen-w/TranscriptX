"""
Understandability Analysis Module for TranscriptX.

This module provides understandability analysis functionality for transcripts,
including readability metrics and text complexity analysis.
"""

from typing import Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.utils.understandability import (
    compute_understandability_metrics,
    plot_understandability_charts,
)
from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.core.utils.notifications import notify_user


class UnderstandabilityAnalysis(AnalysisModule):
    """
    Understandability analysis module.

    This module analyzes readability and text complexity metrics for transcript
    segments, providing per-speaker understandability scores.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the understandability analysis module."""
        super().__init__(config)
        self.module_name = "understandability"

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Perform understandability analysis on transcript segments (pure logic, no I/O).

        Args:
            segments: List of transcript segments
            speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility)

        Returns:
            Dictionary containing understandability analysis results
        """
        from transcriptx.core.utils.speaker_extraction import (
            group_segments_by_speaker,
            get_speaker_display_name,
        )

        # Group segments by speaker using speaker_db_id when available
        grouped_segments = group_segments_by_speaker(segments)

        # Aggregate text by speaker (using grouping_key for uniqueness)
        grouped_texts = {}
        skipped = 0

        for grouping_key, segs in grouped_segments.items():
            display_name = get_speaker_display_name(grouping_key, segs, segments)
            if not display_name or not is_named_speaker(display_name):
                skipped += len(segs)
                continue

            # Combine text from all segments for this speaker
            text = " ".join(seg.get("text", "") for seg in segs)
            grouped_texts[display_name] = text

        # Compute understandability metrics for each speaker
        scores = {
            speaker: compute_understandability_metrics(text)
            for speaker, text in grouped_texts.items()
        }

        # Prepare summary data
        speaker_stats = {speaker: metrics for speaker, metrics in scores.items()}
        if speaker_stats:
            global_stats = {
                k: sum(d[k] for d in speaker_stats.values()) / len(speaker_stats)
                for k in next(iter(speaker_stats.values())).keys()
            }
        else:
            global_stats = {}

        return {
            "scores": scores,
            "speaker_stats": speaker_stats,
            "global_stats": global_stats,
            "skipped": skipped,
        }

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """
        Save results using OutputService (new interface).

        Args:
            results: Analysis results dictionary
            output_service: OutputService instance
        """
        scores = results["scores"]
        base_name = output_service.base_name

        # Save JSON data
        output_service.save_data(scores, "understandability", format_type="json")

        # Save CSV data (per-speaker and global)
        # Note: OutputService should handle CSV, but we may need to use utility function
        # for the specific CSV format expected
        from transcriptx.core.utils.understandability import save_understandability_csv

        output_structure = output_service.get_output_structure()
        save_understandability_csv(scores, output_structure, base_name)

        # Generate and save charts
        plot_understandability_charts(scores, output_structure, base_name)

        # Save summary
        output_service.save_summary(
            results["global_stats"], results["speaker_stats"], analysis_metadata={}
        )

        # Notify about skipped segments
        if results.get("skipped", 0) > 0:
            notify_user(
                f"⚠️ Skipped {results['skipped']} segments with no speaker label.",
                technical=True,
                section="understandability",
            )
