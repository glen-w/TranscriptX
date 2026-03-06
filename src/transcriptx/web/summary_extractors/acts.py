"""
Summary extractor for ACTS analysis.
"""

from typing import Dict, Any
from . import register_extractor


def extract_acts_summary(data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """Extract summary from ACTS analysis data."""
    acts = data.get("acts", [])
    if acts:
        summary["key_metrics"]["Total ACTS"] = len(acts)
        # Count by type
        act_types = {}
        for act in acts:
            act_type = act.get("type", "unknown")
            act_types[act_type] = act_types.get(act_type, 0) + 1
        if act_types:
            summary["key_metrics"]["ACT Types"] = len(act_types)
            most_common = max(act_types.items(), key=lambda x: x[1])
            summary["highlights"].append(
                f"Most common ACT type: {most_common[0]} ({most_common[1]} occurrences)"
            )


register_extractor("acts", extract_acts_summary)
