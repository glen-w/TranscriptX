"""Markdown render for llm_custom_qa artifacts."""

from __future__ import annotations

from typing import Any


def render_custom_qa_markdown(payload: dict[str, Any]) -> str:
    questions = payload.get("questions_requested") or []
    answers = payload.get("answers") or []
    outcome = payload.get("outcome") or ""
    lines = [
        "# Custom Questions",
        "",
        f"Outcome: `{outcome}`",
        f"Questions: {len(questions)}",
        "",
    ]
    if not answers:
        lines.append("_No questions for this run._")
        lines.append("")
        return "\n".join(lines)

    for row in answers:
        if not isinstance(row, dict):
            continue
        idx = row.get("question_index", "?")
        q = str(row.get("question") or "")
        status = row.get("status")
        lines.append(f"## Q{idx}: {q}")
        lines.append("")
        lines.append(f"Status: `{status}`")
        if status == "answered":
            lines.append("")
            lines.append(str(row.get("answer") or ""))
            citations = row.get("citations") or []
            if citations:
                lines.append("")
                lines.append("Citations:")
                for cite in citations:
                    if not isinstance(cite, dict):
                        continue
                    segs = cite.get("segment_indexes") or []
                    quote = str(cite.get("quote") or "").replace("\n", " / ")
                    lines.append(f"- segments {segs}: \"{quote}\"")
        elif status == "abstained":
            lines.append(f"Abstain reason: `{row.get('abstain_reason')}`")
        elif status == "unavailable":
            lines.append(f"System reason: `{row.get('system_reason')}`")
        lines.append("")
    return "\n".join(lines)
