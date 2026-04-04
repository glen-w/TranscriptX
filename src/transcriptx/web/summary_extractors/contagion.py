"""
Summary extractor for contagion analysis.
"""

from typing import Dict, Any
from . import register_extractor


def extract_contagion_summary(data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """Extract summary from contagion analysis data."""
    contagion_data = data.get("contagion", {})
    if contagion_data:
        summary["key_metrics"]["Contagion Events"] = contagion_data.get(
            "total_events", 0
        )
        summary["key_metrics"]["Affected Speakers"] = contagion_data.get(
            "affected_speakers", 0
        )


register_extractor("contagion", extract_contagion_summary)
