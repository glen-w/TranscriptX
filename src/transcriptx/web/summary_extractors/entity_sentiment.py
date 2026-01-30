"""
Summary extractor for entity sentiment analysis.
"""

from typing import Dict, Any
from . import register_extractor


def extract_entity_sentiment_summary(
    data: Dict[str, Any], summary: Dict[str, Any]
) -> None:
    """Extract summary from entity sentiment analysis data."""
    entity_sentiments = data.get("entity_sentiments", {})
    if entity_sentiments:
        summary["key_metrics"]["Entities with Sentiment"] = len(entity_sentiments)
        # Find most positive and negative entities
        entity_scores = {
            entity: info.get("average_sentiment", 0)
            for entity, info in entity_sentiments.items()
        }
        if entity_scores:
            most_positive = max(entity_scores.items(), key=lambda x: x[1])
            most_negative = min(entity_scores.items(), key=lambda x: x[1])
            summary["highlights"].append(
                f"Most positive entity: {most_positive[0]} ({most_positive[1]:.2f})"
            )
            summary["highlights"].append(
                f"Most negative entity: {most_negative[0]} ({most_negative[1]:.2f})"
            )


register_extractor("entity_sentiment", extract_entity_sentiment_summary)
