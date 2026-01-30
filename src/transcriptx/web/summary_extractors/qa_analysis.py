"""
Summary extractor for Q&A analysis.
"""

from typing import Dict, Any
from . import register_extractor


def extract_qa_analysis_summary(data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """Extract summary from Q&A analysis data."""
    qa_data = data.get("qa_analysis", {})
    if qa_data:
        summary["key_metrics"]["Questions"] = qa_data.get("question_count", 0)
        summary["key_metrics"]["Answers"] = qa_data.get("answer_count", 0)
        summary["key_metrics"]["Q&A Pairs"] = qa_data.get("pairs", 0)


register_extractor("qa_analysis", extract_qa_analysis_summary)
