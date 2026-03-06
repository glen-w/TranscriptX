"""
Summary extractor for stats analysis.
"""

from typing import Dict, Any
from . import register_extractor


def extract_stats_summary(data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """Extract summary from stats analysis data."""
    stats = data.get("statistics", {})
    if stats:
        summary["key_metrics"]["Total Words"] = stats.get("total_words", 0)
        summary["key_metrics"]["Total Segments"] = stats.get("total_segments", 0)
        summary["key_metrics"]["Average Words per Segment"] = stats.get(
            "avg_words_per_segment", 0
        )


register_extractor("stats", extract_stats_summary)
