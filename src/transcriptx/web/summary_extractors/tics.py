"""
Summary extractor for tics analysis.
"""

from typing import Dict, Any
from . import register_extractor


def extract_tics_summary(data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """Extract summary from tics analysis data."""
    tics = data.get("tics", [])
    if tics:
        summary["key_metrics"]["Total Tics"] = len(tics)
        # Count by type
        tic_types = {}
        for tic in tics:
            tic_type = tic.get("type", "unknown")
            tic_types[tic_type] = tic_types.get(tic_type, 0) + 1
        if tic_types:
            summary["key_metrics"]["Tic Types"] = len(tic_types)


register_extractor("tics", extract_tics_summary)
