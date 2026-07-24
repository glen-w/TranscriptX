"""Markdown render for llm_custom_qa artifacts."""

from __future__ import annotations

from typing import Any


def _question_label(row: dict[str, Any], questions: list[Any]) -> str:
    q = row.get("question")
    if q:
        return str(q)
    qid = row.get("question_id")
    if qid and questions and isinstance(questions[0], dict):
        for item in questions:
            if isinstance(item, dict) and item.get("question_id") == qid:
                return str(item.get("text") or qid)
    idx = row.get("question_index")
    if isinstance(idx, int) and 0 <= idx < len(questions):
        item = questions[idx]
        if isinstance(item, dict):
            return str(item.get("text") or item)
        return str(item)
    return str(qid or idx or "?")


def _render_row(lines: list[str], row: dict[str, Any], questions: list[Any]) -> None:
    if not isinstance(row, dict):
        return
    q = _question_label(row, questions)
    scope = row.get("scope") or "global"
    speaker = row.get("speaker_key")
    header = f"## {q}"
    if scope == "per_speaker" and speaker:
        header = f"## [{speaker}] {q}"
    lines.append(header)
    lines.append("")
    status = row.get("status")
    if status == "answered":
        lines.append("### Answer")
        lines.append(str(row.get("answer") or ""))
        reasoning = row.get("reasoning")
        if reasoning:
            lines.append("")
            lines.append("### Evidence explanation")
            lines.append(str(reasoning))
        citations = row.get("citations") or []
        if citations:
            lines.append("")
            lines.append("### Citations")
            for cite in citations:
                if not isinstance(cite, dict):
                    continue
                segs = cite.get("segment_indexes") or []
                quote = str(cite.get("quote") or "").replace("\n", " / ")
                lines.append(f'- segments {segs}: "{quote}"')
        evidence_used = row.get("evidence_used") or {}
        if isinstance(evidence_used, dict) and evidence_used.get("pack_ids_rendered"):
            lines.append("")
            lines.append(
                f"Evidence used: packs={evidence_used.get('pack_ids_rendered')}, "
                f"transcript={evidence_used.get('use_transcript')}"
            )
    elif status == "abstained":
        lines.append(f"Status: `{status}`")
        lines.append(f"Abstain reason: `{row.get('abstain_reason')}`")
    elif status == "unavailable":
        lines.append(f"Status: `{status}`")
        lines.append(f"System reason: `{row.get('system_reason')}`")
    elif status:
        lines.append(f"Status: `{status}`")
    lines.append("")


def render_custom_qa_markdown(payload: dict[str, Any]) -> str:
    questions = payload.get("questions_requested") or []
    answers = payload.get("answers") or []
    speaker_answers = payload.get("speaker_answers") or []
    outcome = payload.get("outcome") or ""
    lines = [
        "# Custom Questions",
        "",
        f"Outcome: `{outcome}`",
        f"Questions: {len(questions)}",
        "",
    ]
    if not answers and not speaker_answers:
        lines.append("_No questions for this run._")
        lines.append("")
        return "\n".join(lines)

    for row in answers:
        _render_row(lines, row, questions)

    for block in speaker_answers:
        if not isinstance(block, dict):
            continue
        for row in block.get("answers") or []:
            if isinstance(row, dict) and row.get("speaker_key") is None:
                row = {**row, "speaker_key": block.get("speaker_key")}
            _render_row(lines, row, questions)

    return "\n".join(lines)
