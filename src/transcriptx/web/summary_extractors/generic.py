"""
Generic summary extractor for unknown modules.
"""

from typing import Dict, Any
from . import register_extractor


def extract_generic_summary(data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """
    Extract generic summary from any analysis data.

    This is a fallback extractor that tries to find common patterns
    in the data structure.
    """
    # Try to find common fields
    if "summary" in data:
        summary_data = data["summary"]
        if isinstance(summary_data, dict):
            summary["key_metrics"].update(summary_data)

    # Look for common statistics
    if "statistics" in data:
        stats = data["statistics"]
        if isinstance(stats, dict):
            summary["key_metrics"].update(
                {k: v for k, v in stats.items() if isinstance(v, (int, float, str))}
            )

    # Look for counts
    for key in ["count", "total", "items", "results"]:
        if key in data:
            value = data[key]
            if isinstance(value, (int, float)):
                summary["key_metrics"][key.title()] = value
            elif isinstance(value, (list, dict)):
                summary["key_metrics"][key.title()] = len(value)


# Register the generic extractor (will be used as fallback)
register_extractor("__generic__", extract_generic_summary)
