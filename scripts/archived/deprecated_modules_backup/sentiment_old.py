"""
Sentiment Analysis Module for TranscriptX.

This module provides sentiment analysis capabilities using the VADER (Valence Aware
Dictionary and sEntiment Reasoner) sentiment analysis tool. VADER is specifically
attuned to sentiments expressed in social media and is particularly good at analyzing
conversational text.

The module analyzes each segment of a transcript and assigns sentiment scores:
- compound: Overall sentiment score (-1 to +1, where -1 is very negative, +1 is very positive)
- positive: Positive sentiment score (0 to 1)
- negative: Negative sentiment score (0 to 1)
- neutral: Neutral sentiment score (0 to 1)

Features:
- Per-speaker sentiment analysis with rolling sentiment plots
- Multi-speaker sentiment comparison
- CSV and JSON output formats
- Integration with speaker mapping system
- Comprehensive data export for further analysis

VADER Sentiment Analysis:
VADER is a lexicon and rule-based sentiment analysis tool that is specifically
attuned to sentiments expressed in social media. It's particularly good at
analyzing conversational text because it:
- Handles emoticons and emojis
- Understands context-dependent words
- Accounts for capitalization and punctuation
- Provides compound scores that are easy to interpret
"""

# Configure matplotlib to use non-interactive backend to prevent threading issues
# This is necessary when running in environments without display or in multi-threaded environments
import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend
import os
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

# Configure NLTK data path BEFORE importing SentimentIntensityAnalyzer
# This ensures NLTK can find the project's nltk_data directory
try:
    import nltk

    # Get the project root directory (go up from src/transcriptx/core/analysis/sentiment.py)
    project_root = Path(__file__).parent.parent.parent.parent.parent
    nltk_data_dir = project_root / "nltk_data"

    # Add project's nltk_data directory to NLTK's data path if it exists
    if nltk_data_dir.exists():
        nltk.data.path.insert(0, str(nltk_data_dir))
except (ImportError, Exception):
    # NLTK not installed or configuration failed, continue anyway
    pass

import matplotlib.pyplot as plt
from nltk.sentiment.vader import SentimentIntensityAnalyzer

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.core.utils.notifications import notify_user
from transcriptx.io import save_transcript
from transcriptx.core.utils.path_utils import get_enriched_transcript_path
from transcriptx.core.utils.nlp_utils import preprocess_for_sentiment

# Initialize the VADER sentiment analyzer
# VADER is pre-trained and doesn't require additional training data
# It uses a lexicon of words with sentiment scores and rules for context
sia = SentimentIntensityAnalyzer()


class SentimentAnalysis(AnalysisModule):
    """
    Sentiment analysis module using VADER sentiment analyzer.

    This module analyzes sentiment for each segment and provides:
    - Per-segment sentiment scores
    - Per-speaker sentiment analysis
    - Multi-speaker sentiment comparison
    - Rolling sentiment plots
    - Data export in JSON and CSV formats
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the sentiment analysis module."""
        super().__init__(config)
        self.module_name = "sentiment"
        self.sia = SentimentIntensityAnalyzer()

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Perform sentiment analysis on transcript segments (pure logic, no I/O).

        Args:
            segments: List of transcript segments
            speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility)

        Returns:
            Dictionary containing sentiment analysis results
        """
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )

        # Calculate sentiment scores for each segment
        for seg in segments:
            text = seg.get("text", "")
            seg["sentiment"] = self._score_sentiment(text)

        # Group segments by speaker for analysis
        speaker_segments = defaultdict(list)
        all_rows = []

        for seg in segments:
            speaker_info = extract_speaker_info(seg)
            if speaker_info is None:
                continue
            speaker = get_speaker_display_name(
                speaker_info.grouping_key, [seg], segments
            )

            # Skip unnamed speakers
            if not speaker or not is_named_speaker(speaker):
                continue

            speaker_segments[speaker].append(seg)

            # Prepare data for export
            sentiment = seg.get("sentiment", {})
            row = {
                "speaker": speaker,
                "start": seg.get("start", 0),
                "text": seg.get("text", ""),
                "compound": sentiment.get("compound"),
                "pos": sentiment.get("pos"),
                "neu": sentiment.get("neu"),
                "neg": sentiment.get("neg"),
            }
            all_rows.append(row)

        # Generate per-speaker analysis
        speaker_stats = {}
        for speaker, segs in speaker_segments.items():
            scores = [s.get("sentiment", {}) for s in segs]
            if not scores:
                continue
            speaker_stats[speaker] = {
                "count": len(scores),
                "compound_mean": sum(s.get("compound", 0) for s in scores)
                / len(scores),
                "pos_mean": sum(s.get("pos", 0) for s in scores) / len(scores),
                "neu_mean": sum(s.get("neu", 0) for s in scores) / len(scores),
                "neg_mean": sum(s.get("neg", 0) for s in scores) / len(scores),
            }

        # Aggregate global stats
        if all_rows:
            global_stats = {
                "count": len(all_rows),
                "compound_mean": sum(
                    r["compound"] for r in all_rows if r["compound"] is not None
                )
                / len(all_rows),
                "pos_mean": sum(r["pos"] for r in all_rows if r["pos"] is not None)
                / len(all_rows),
                "neu_mean": sum(r["neu"] for r in all_rows if r["neu"] is not None)
                / len(all_rows),
                "neg_mean": sum(r["neg"] for r in all_rows if r["neg"] is not None)
                / len(all_rows),
            }
        else:
            global_stats = {}

        result = {
            "segments_with_sentiment": segments,
            "speaker_segments": dict(speaker_segments),
            "all_rows": all_rows,
            "speaker_stats": speaker_stats,
            "global_stats": global_stats,
            "speaker_map": speaker_map,
        }
        # Backward-compatible key
        result["segments"] = segments
        return result

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """
        Save results using OutputService (new interface).

        Args:
            results: Analysis results dictionary
            output_service: OutputService instance
        """
        segments = results["segments_with_sentiment"]
        speaker_segments = results["speaker_segments"]
        all_rows = results["all_rows"]
        speaker_map = results["speaker_map"]
        base_name = output_service.base_name

        # Save enriched transcript with sentiment scores
        enriched_path = get_enriched_transcript_path(
            output_service.transcript_path, "sentiment"
        )
        os.makedirs(os.path.dirname(enriched_path), exist_ok=True)
        save_transcript(segments, enriched_path)

        # Save complete transcript-wide sentiment data
        output_service.save_data(all_rows, "sentiment", format_type="json")
        output_service.save_data(all_rows, "sentiment", format_type="csv")

        # Generate per-speaker analysis and visualizations
        for speaker, segs in speaker_segments.items():
            # Create rolling sentiment plot
            fig = self._create_rolling_sentiment_plot(segs, speaker)
            output_service.save_chart(
                fig, f"{speaker}_rolling_sentiment", speaker=speaker
            )

            # Prepare speaker data for export
            speaker_data = [
                {
                    "start": s.get("start", 0),
                    "text": s.get("text", ""),
                    **s.get("sentiment", {}),
                }
                for s in segs
            ]

            # Save speaker data
            output_service.save_data(
                speaker_data,
                f"{speaker}_sentiment",
                format_type="json",
                subdirectory="speakers",
            )
            output_service.save_data(
                speaker_data,
                f"{speaker}_sentiment",
                format_type="csv",
                subdirectory="speakers",
            )

        # Generate multi-speaker comparison plot
        fig = self._create_multi_speaker_plot(segments, speaker_map)
        output_service.save_chart(fig, "multi_speaker_sentiment")

        # Save summary
        output_service.save_summary(
            results["global_stats"], results["speaker_stats"], analysis_metadata={}
        )

    def _score_sentiment(self, text: str, preprocess: bool = False) -> dict:
        """Calculate sentiment scores for a given text using VADER."""
        if preprocess:
            text = preprocess_for_sentiment(text)
            if not text:
                return {"compound": 0.0, "pos": 0.0, "neg": 0.0, "neu": 1.0}
        return self.sia.polarity_scores(text)

    def _create_rolling_sentiment_plot(self, segments: List[Dict], speaker_name: str):
        """Create rolling sentiment plot for a specific speaker."""
        x_vals = []
        y_vals = []

        for seg in segments:
            sentiment = seg.get("sentiment", {})
            compound = sentiment.get("compound")
            if compound is not None:
                x_vals.append(seg.get("start", 0) / 60.0)
                y_vals.append(compound)

        if not y_vals:
            return None

        plt.figure(figsize=(12, 4))
        plt.plot(x_vals, y_vals, marker="o", linestyle="-", alpha=0.7)
        plt.title(f"Rolling Sentiment: {speaker_name}")
        plt.xlabel("Time (minutes)")
        plt.ylabel("Compound Sentiment Score")
        plt.axhline(0, color="black", linestyle="--", linewidth=0.8)
        plt.grid(True)
        plt.tight_layout()

        return plt.gcf()

    def _create_multi_speaker_plot(
        self, segments: List[Dict], speaker_map: Dict[str, str]
    ):
        """Create multi-speaker sentiment comparison plot."""
        speaker_scores = defaultdict(list)
        speaker_times = defaultdict(list)

        for seg in segments:
            raw_id = seg.get("speaker")
            name = speaker_map.get(raw_id, raw_id)

            if not is_named_speaker(name):
                continue

            sentiment = seg.get("sentiment", {})
            compound = sentiment.get("compound")
            if compound is not None:
                speaker_scores[name].append(compound)
                speaker_times[name].append(seg.get("start", 0) / 60.0)

        if not any(speaker_scores.values()):
            notify_user(
                "⚠️ No valid sentiment scores found — skipping plot.",
                technical=True,
                section="sentiment",
            )
            return None

        plt.figure(figsize=(14, 5))

        for speaker in speaker_scores:
            if speaker_scores[speaker]:
                plt.plot(speaker_times[speaker], speaker_scores[speaker], label=speaker)

        plt.axhline(0, linestyle="--", color="black", linewidth=0.8)
        plt.title("Sentiment Over Time – All Speakers")
        plt.xlabel("Time (minutes)")
        plt.ylabel("Compound Sentiment Score")
        plt.legend()
        plt.tight_layout()

        return plt.gcf()


# Legacy functions for backward compatibility
def analyze_sentiment_from_file(path: str) -> None:
    """
    Analyze sentiment for a transcript file (DEPRECATED).

    This function is maintained for backward compatibility. New code should use
    SentimentAnalysis class with PipelineContext.

    Args:
        path: Path to the transcript JSON file to analyze
    """
    warnings.warn(
        "analyze_sentiment_from_file is deprecated. Use SentimentAnalysis with PipelineContext instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    from transcriptx.core.pipeline.pipeline_context import PipelineContext
    from transcriptx.core.analysis.sentiment import SentimentAnalysis

    context = PipelineContext(path)
    analyzer = SentimentAnalysis()
    analyzer.run_from_context(context)


def analyze_sentiment(
    segments: list, path: str, base_name: str, transcript_dir: str, speaker_map: dict
) -> None:
    """
    Perform sentiment analysis on transcript segments (DEPRECATED).

    This function is maintained for backward compatibility. New code should use
    SentimentAnalysis.analyze() method.

    Args:
        segments: List of transcript segments
        path: Original path to the transcript file
        base_name: Base name for output files
        transcript_dir: Directory where results will be saved
        speaker_map: Mapping from speaker IDs to human-readable names
    """
    warnings.warn(
        "analyze_sentiment is deprecated. Use SentimentAnalysis class instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Create context and analyzer
    from transcriptx.core.analysis.sentiment import SentimentAnalysis

    # Note: This is a simplified migration - full migration would require
    # updating all callers to use the new interface
    analyzer = SentimentAnalysis()
    results = analyzer.analyze(segments, speaker_map)

    # Create output service and save
    from transcriptx.core.output.output_service import create_output_service

    output_service = create_output_service(path, "sentiment")
    analyzer.save_results(results, output_service=output_service)


def score_sentiment(text: str, preprocess: bool = False) -> dict:
    """
    Calculate sentiment scores for a given text using VADER.

    Args:
        text: The text to analyze for sentiment
        preprocess: Whether to preprocess text to remove tics before analysis

    Returns:
        Dictionary containing sentiment scores
    """
    if preprocess:
        text = preprocess_for_sentiment(text)
        if not text:
            return {"compound": 0.0, "pos": 0.0, "neg": 0.0, "neu": 1.0}
    return sia.polarity_scores(text)


def compute_rolling_sentiment(
    segments: list, speaker_name: str, output_path: str
) -> None:
    """
    Generate a rolling sentiment plot for a specific speaker (DEPRECATED).

    This function is maintained for backward compatibility.
    """
    warnings.warn(
        "compute_rolling_sentiment is deprecated. Use SentimentAnalysis class instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    analyzer = SentimentAnalysis()
    fig = analyzer._create_rolling_sentiment_plot(segments, speaker_name)
    if fig:
        fig.savefig(output_path)
        plt.close(fig)


def plot_multi_speaker_sentiment(
    segments: list, speaker_map: dict, output_path: str
) -> None:
    """
    Generate a multi-speaker sentiment comparison plot (DEPRECATED).

    This function is maintained for backward compatibility.
    """
    warnings.warn(
        "plot_multi_speaker_sentiment is deprecated. Use SentimentAnalysis class instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    analyzer = SentimentAnalysis()
    fig = analyzer._create_multi_speaker_plot(segments, speaker_map)
    if fig:
        fig.savefig(output_path)
        plt.close(fig)
