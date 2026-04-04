"""
Summary extractor for understandability analysis.
"""

from typing import Dict, Any
from . import register_extractor


def extract_understandability_summary(
    data: Dict[str, Any], summary: Dict[str, Any]
) -> None:
    """Extract summary from understandability analysis data."""
    scores = data.get("understandability_scores", {})
    if scores:
        summary["key_metrics"]["Average Score"] = f"{scores.get('average', 0):.2f}"
        summary["key_metrics"]["Readability Level"] = scores.get(
            "readability_level", "Unknown"
        )


register_extractor("understandability", extract_understandability_summary)
