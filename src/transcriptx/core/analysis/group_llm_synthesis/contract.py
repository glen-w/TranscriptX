"""Parse and validate model JSON responses for group synthesis."""

from __future__ import annotations

import json
from typing import Any, Dict

from transcriptx.core.analysis.group_llm_synthesis import errors as err
from transcriptx.core.analysis.group_llm_synthesis.schemas import MAX_SUMMARY_CHARS
from transcriptx.core.analysis.llm_support.json_parse import loads_llm_json_document
from transcriptx.core.llm.errors import LLMResponseError


def parse_group_summary_json(
    text: str,
    *,
    max_chars: int = MAX_SUMMARY_CHARS,
) -> Dict[str, Any]:
    try:
        data = loads_llm_json_document(text)
    except json.JSONDecodeError as exc:
        raise LLMResponseError(
            f"Group summary output is not valid JSON: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise LLMResponseError("Group summary JSON must be an object")
    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise LLMResponseError("Group summary JSON missing non-empty 'summary' string")
    if len(summary) > max_chars:
        raise LLMResponseError(f"Group summary exceeds max length ({max_chars} chars)")
    return {"summary": summary.strip()}


def response_error_code(exc: BaseException) -> str:
    msg = str(exc).lower()
    if "exceeds max length" in msg or "oversized" in msg:
        return err.SUMMARY_OVERSIZED
    return err.LLM_INVALID_RESPONSE
