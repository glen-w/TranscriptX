"""
Summary extractor for topic modeling analysis.
"""

from typing import Dict, Any
from . import register_extractor


def extract_topic_modeling_summary(
    data: Dict[str, Any], summary: Dict[str, Any]
) -> None:
    """Extract summary from topic modeling analysis data."""
    lda_results = data.get("lda_results", {})
    nmf_results = data.get("nmf_results", {})

    if lda_results:
        topics = lda_results.get("topics", [])
        summary["key_metrics"]["LDA Topics"] = len(topics)

    if nmf_results:
        topics = nmf_results.get("topics", [])
        summary["key_metrics"]["NMF Topics"] = len(topics)

    if lda_results and lda_results.get("topics"):
        summary["highlights"].append(
            f"Identified {len(lda_results['topics'])} main topics"
        )


register_extractor("topic_modeling", extract_topic_modeling_summary)
