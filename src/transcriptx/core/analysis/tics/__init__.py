# src/transcriptx/core/tics.py

"""
Verbal Tics Analysis Module for TranscriptX.
"""

import os
from collections import Counter, defaultdict
from typing import Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.io import save_transcript
from transcriptx.core.utils.nlp_utils import ALL_VERBAL_TICS
from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.core.utils.path_utils import get_enriched_transcript_path
from transcriptx.core.utils.lazy_imports import lazy_pyplot
from transcriptx.core.utils.viz_ids import VIZ_TICS_SPEAKER
from transcriptx.core.viz.specs import BarCategoricalSpec

plt = lazy_pyplot()


# Keep extract_tics_and_top_words as utility function (used by stats module)
def extract_tics_and_top_words(grouped_text: dict, top_n: int = 100) -> tuple:
    """
    Extracts verbal tics and top N words/bigrams per speaker.
    Returns a tuple: (per_speaker_tics, per_speaker_common)
    """
    per_speaker_tics = {}
    per_speaker_common = {}

    for speaker, texts in grouped_text.items():
        if not is_named_speaker(speaker):
            continue

        tokens = []
        bigrams = []

        for text in texts:
            words = text.lower().split()
            tokens.extend(words)
            bigrams.extend(
                ["_".join(pair) for pair in zip(words, words[1:], strict=False)]
            )

        all_items = tokens + bigrams
        counter = Counter(all_items)

        common = counter.most_common(top_n)
        tics = [word for word in tokens if word in ALL_VERBAL_TICS]

        per_speaker_common[speaker] = common
        per_speaker_tics[speaker] = dict(Counter(tics))

    return per_speaker_tics, per_speaker_common


class TicsAnalysis(AnalysisModule):
    """
    Verbal tics analysis module.

    This module analyzes verbal tics (filler words) in transcript segments
    and provides per-speaker tic counts and visualizations.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the tics analysis module."""
        super().__init__(config)
        self.module_name = "tics"

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Perform tics analysis on transcript segments (pure logic, no I/O).

        Args:
            segments: List of transcript segments
            speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility)

        Returns:
            Dictionary containing tics analysis results
        """
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )

        tic_counts = defaultdict(Counter)

        for seg in segments:
            if not isinstance(seg, dict):
                continue

            speaker_info = extract_speaker_info(seg)
            if speaker_info is None:
                continue
            speaker = get_speaker_display_name(
                speaker_info.grouping_key, [seg], segments
            )
            if not speaker or not is_named_speaker(speaker):
                continue

            text = seg.get("text", "").lower()
            words = text.split()
            for word in words:
                if word in ALL_VERBAL_TICS:
                    tic_counts[speaker][word] += 1

        # Prepare summary data
        speaker_stats = {
            speaker: dict(counter) for speaker, counter in tic_counts.items()
        }
        total_tics = sum(sum(counter.values()) for counter in tic_counts.values())
        global_stats = {"total_tics": total_tics}
        for speaker, counter in tic_counts.items():
            for tic, count in counter.items():
                global_stats[tic] = global_stats.get(tic, 0) + count

        return {
            "tic_counts": dict(tic_counts),
            "speaker_stats": speaker_stats,
            "global_stats": global_stats,
            "segments": segments,  # Keep segments for enriched transcript
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
        tic_counts = results["tic_counts"]
        segments = results["segments"]
        base_name = output_service.base_name

        # Save enriched transcript
        enriched_path = get_enriched_transcript_path(
            output_service.transcript_path, "tics"
        )
        os.makedirs(os.path.dirname(enriched_path), exist_ok=True)
        save_transcript(segments, enriched_path)

        # Save JSON summary
        json_out = {speaker: dict(counter) for speaker, counter in tic_counts.items()}
        output_service.save_data(json_out, "tics_summary", format_type="json")

        # Save human-readable text summary
        summary_lines = []
        for speaker, counter in tic_counts.items():
            summary_lines.append(f"Speaker: {speaker}\n")
            for tic, count in counter.most_common():
                summary_lines.append(f"  {tic}: {count}\n")
            summary_lines.append("\n")
        summary_text = "".join(summary_lines)
        output_service.save_data(summary_text, "tics_summary", format_type="txt")

        # Generate and save bar charts
        for speaker, counter in tic_counts.items():
            top_tics = counter.most_common(10)
            if not top_tics:
                continue

            labels = [tic for tic, _ in top_tics]
            values = [count for _, count in top_tics]
            spec = BarCategoricalSpec(
                viz_id=VIZ_TICS_SPEAKER,
                module=self.module_name,
                name="tics",
                scope="speaker",
                speaker=speaker,
                chart_intent="bar_categorical",
                title=f"Top Verbal Tics: {speaker}",
                x_label="Tic",
                y_label="Count",
                categories=labels,
                values=values,
            )
            output_service.save_chart(spec, chart_type="tics")

        # Save summary
        output_service.save_summary(
            results["global_stats"], results["speaker_stats"], analysis_metadata={}
        )

    def _create_tic_chart(self, speaker: str, top_tics: List[tuple]) -> Any:
        """Create bar chart for tics."""
        labels, values = zip(*top_tics, strict=False)
        plt.figure(figsize=(8, 4))
        bars = plt.bar(labels, values, color="salmon")
        plt.title(f"Top Verbal Tics: {speaker}")
        plt.ylabel("Count")
        plt.xticks(rotation=30)
        for bar, count in zip(bars, values, strict=False):
            plt.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                str(count),
                ha="center",
                va="bottom",
            )
        plt.tight_layout()
        return plt.gcf()
