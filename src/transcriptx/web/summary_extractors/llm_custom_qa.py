"""Summary extractor for llm_custom_qa analysis."""

from __future__ import annotations

from typing import Any, Dict

from . import register_extractor


def extract_llm_custom_qa_summary(
    data: Dict[str, Any], summary: Dict[str, Any]
) -> None:
    questions = data.get("questions_requested")
    answers = data.get("answers")
    if isinstance(questions, list):
        summary["key_metrics"]["Custom questions"] = len(questions)
    if isinstance(answers, list):
        status_counts: Dict[str, int] = {}
        for row in answers:
            if not isinstance(row, dict):
                continue
            status = str(row.get("status") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        for status, count in status_counts.items():
            summary["key_metrics"][f"QA {status}"] = count
    outcome = data.get("outcome")
    if outcome:
        summary["key_metrics"]["QA outcome"] = str(outcome)


register_extractor("llm_custom_qa", extract_llm_custom_qa_summary)
