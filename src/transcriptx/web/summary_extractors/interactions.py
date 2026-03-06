"""
Summary extractor for interactions analysis.
"""

from typing import Dict, Any
from . import register_extractor


def extract_interactions_summary(data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """Extract summary from interactions analysis data."""
    interactions = data.get("interactions", [])
    if interactions:
        summary["key_metrics"]["Total Interactions"] = len(interactions)
        summary["key_metrics"]["Unique Speaker Pairs"] = len(
            set(
                tuple(sorted([i.get("speaker1"), i.get("speaker2")]))
                for i in interactions
                if i.get("speaker1") and i.get("speaker2")
            )
        )


register_extractor("interactions", extract_interactions_summary)
