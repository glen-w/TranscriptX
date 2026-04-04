"""
Summary extractor for NER analysis.
"""

from typing import Dict, Any
from . import register_extractor


def extract_ner_summary(data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """Extract summary from NER analysis data."""
    entities = data.get("entities", {})
    if entities:
        total_entities = sum(len(entity_list) for entity_list in entities.values())
        summary["key_metrics"]["Total Entities"] = total_entities
        summary["key_metrics"]["Entity Types"] = len(entities)

        # Find most common entity type
        entity_counts = {etype: len(elist) for etype, elist in entities.items()}
        if entity_counts:
            most_common = max(entity_counts.items(), key=lambda x: x[1])
            summary["highlights"].append(
                f"Most common entity type: {most_common[0]} ({most_common[1]} entities)"
            )


register_extractor("ner", extract_ner_summary)
