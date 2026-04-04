"""
Summary extractor for sentiment analysis.
"""

from typing import Dict, Any
from . import register_extractor


def extract_sentiment_summary(data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """Extract summary from sentiment analysis data."""
    global_stats = data.get("global_stats", {})
    speaker_stats = data.get("speaker_stats", {})

    if global_stats:
        summary["key_metrics"][
            "Overall Sentiment"
        ] = f"{global_stats.get('compound_mean', 0):.2f}"
        summary["key_metrics"]["Positive Segments"] = global_stats.get(
            "positive_count", 0
        )
        summary["key_metrics"]["Negative Segments"] = global_stats.get(
            "negative_count", 0
        )
        summary["key_metrics"]["Neutral Segments"] = global_stats.get(
            "neutral_count", 0
        )

    if speaker_stats:
        summary["key_metrics"]["Speakers Analyzed"] = len(speaker_stats)
        # Find most positive and negative speakers
        speaker_scores = {
            speaker: stats.get("compound_mean", 0)
            for speaker, stats in speaker_stats.items()
        }
        if speaker_scores:
            most_positive = max(speaker_scores.items(), key=lambda x: x[1])
            most_negative = min(speaker_scores.items(), key=lambda x: x[1])
            summary["highlights"].append(
                f"Most positive speaker: {most_positive[0]} ({most_positive[1]:.2f})"
            )
            summary["highlights"].append(
                f"Most negative speaker: {most_negative[0]} ({most_negative[1]:.2f})"
            )


register_extractor("sentiment", extract_sentiment_summary)
