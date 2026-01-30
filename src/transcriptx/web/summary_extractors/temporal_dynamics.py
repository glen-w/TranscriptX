"""
Summary extractor for temporal dynamics analysis.
"""

from typing import Dict, Any
from . import register_extractor


def extract_temporal_dynamics_summary(
    data: Dict[str, Any], summary: Dict[str, Any]
) -> None:
    """Extract summary from temporal dynamics analysis data."""
    dynamics = data.get("temporal_dynamics", {})
    if dynamics:
        summary["key_metrics"]["Time Periods Analyzed"] = dynamics.get("periods", 0)
        summary["key_metrics"]["Trends Identified"] = dynamics.get("trends", 0)


register_extractor("temporal_dynamics", extract_temporal_dynamics_summary)
