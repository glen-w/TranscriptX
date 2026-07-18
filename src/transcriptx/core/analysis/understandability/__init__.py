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
from transcriptx.utils.text_utils import is_turn_taking_speaker_label
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
        from collections import defaultdict

        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )

        # Group segments by speaker, falling back to the raw diarization label
        # (e.g. "SPEAKER_00") when a segment has no stable id / human-readable name,
        # so readability metrics are still produced for un-named transcripts.
        grouped_segments: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
        skipped = 0
        for seg in segments:
            info = extract_speaker_info(seg)
            if info is not None:
                grouping_key = info.grouping_key
            else:
                label = seg.get("speaker")
                grouping_key = str(label) if label else None
            if grouping_key is None:
                skipped += 1
                continue
            grouped_segments[grouping_key].append(seg)

        # Aggregate text by speaker (using grouping_key for uniqueness)
        grouped_texts = {}

        for grouping_key, segs in grouped_segments.items():
            display_name = get_speaker_display_name(grouping_key, segs, segments)
            if not display_name or not is_turn_taking_speaker_label(display_name):
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

        # Generate and save charts (output_service required so figures are persisted)
        plot_understandability_charts(
            scores, output_structure, base_name, output_service
        )

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
