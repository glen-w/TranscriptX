"""Summary extractor for BERTopic analysis."""

from typing import Any, Dict

from . import register_extractor


def extract_bertopic_summary(data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """Extract summary from BERTopic analysis data."""
    topics = data.get("topics") or []
    meta = data.get("meta") or {}
    non_outlier = [t for t in topics if int(t.get("topic_id", -1)) != -1]
    summary["key_metrics"]["BERTopic Topics"] = len(non_outlier)
    if meta.get("all_outlier"):
        summary["highlights"].append("All documents classified as outlier topics")
    elif non_outlier:
        summary["highlights"].append(f"Identified {len(non_outlier)} BERTopic topics")


register_extractor("bertopic", extract_bertopic_summary)
