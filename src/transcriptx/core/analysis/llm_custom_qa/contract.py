"""Two-pass row processing and cache key construction."""

from __future__ import annotations

from typing import Any, Optional

from transcriptx.core.analysis.llm_custom_qa.artifact_schema import (
    compute_outcome,
    empty_diagnostics,
)
from transcriptx.core.analysis.llm_custom_qa.constants import (
    ABSENCE_DETECTOR_VERSION,
    MODULE_VERSION,
    PROMPT_VERSION,
    SCHEMA_ID,
)
from transcriptx.core.analysis.llm_custom_qa.model_schema import (
    extract_question_index,
    try_parse_answer_row,
)
from transcriptx.core.analysis.llm_support.hashing import sha256_canonical_json


def process_raw_answers(
    raw_answers: list[Any],
    *,
    questions_requested: list[str] | tuple[str, ...],
    max_answer_chars: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Two-pass algorithm → canonical rows (pre-grounding) + diagnostics counters."""
    n = len(questions_requested)
    diagnostics = empty_diagnostics()

    # Pass A
    valid_by_index: dict[int, Any] = {}
    invalid_by_index: dict[int, Any] = {}
    for raw in raw_answers:
        idx = extract_question_index(raw)
        if idx is None or idx < 0 or idx >= n:
            diagnostics["extra_or_duplicate_rows_dropped"] += 1
            continue
        row = try_parse_answer_row(raw)
        if row is None:
            if idx not in invalid_by_index and idx not in valid_by_index:
                invalid_by_index[idx] = raw
            else:
                diagnostics["extra_or_duplicate_rows_dropped"] += 1
            continue
        # Over-limit answers: reject as invalid candidate (not clip)
        if (
            row.status == "answered"
            and row.answer is not None
            and len(row.answer) > max_answer_chars
        ):
            diagnostics["answers_over_limit"] += 1
            if idx not in invalid_by_index and idx not in valid_by_index:
                invalid_by_index[idx] = raw
            else:
                diagnostics["extra_or_duplicate_rows_dropped"] += 1
            continue
        if idx in valid_by_index:
            diagnostics["extra_or_duplicate_rows_dropped"] += 1
            continue
        if idx in invalid_by_index:
            # First fully valid still wins over prior invalid
            del invalid_by_index[idx]
        valid_by_index[idx] = row

    # Pass B
    answers: list[dict[str, Any]] = []
    for i in range(n):
        question = questions_requested[i]
        if i in valid_by_index:
            row = valid_by_index[i]
            if row.status == "answered":
                answers.append(
                    {
                        "question_index": i,
                        "question": question,
                        "status": "answered",
                        "answer": row.answer,
                        "abstain_reason": None,
                        "system_reason": None,
                        "confidence": row.confidence,
                        "citations": [],
                        "grounding": {
                            "quotes_requested": len(row.quotes),
                            "quotes_grounded": 0,
                            "citations_emitted": 0,
                            "citations_truncated": 0,
                            "cross_segment_citations": 0,
                        },
                        "_model_quotes": list(row.quotes),
                    }
                )
            else:
                answers.append(
                    {
                        "question_index": i,
                        "question": question,
                        "status": "abstained",
                        "answer": None,
                        "abstain_reason": row.abstain_reason,
                        "system_reason": None,
                        "confidence": row.confidence,
                        "citations": [],
                        "grounding": {
                            "quotes_requested": 0,
                            "quotes_grounded": 0,
                            "citations_emitted": 0,
                            "citations_truncated": 0,
                            "cross_segment_citations": 0,
                        },
                        "_model_quotes": [],
                    }
                )
        elif i in invalid_by_index:
            diagnostics["response_invalid_count"] += 1
            answers.append(_unavailable_row(i, question, "response_invalid"))
        else:
            diagnostics["response_incomplete_count"] += 1
            answers.append(_unavailable_row(i, question, "response_incomplete"))

    return answers, diagnostics


def _unavailable_row(
    index: int, question: str, system_reason: str
) -> dict[str, Any]:
    return {
        "question_index": index,
        "question": question,
        "status": "unavailable",
        "answer": None,
        "abstain_reason": None,
        "system_reason": system_reason,
        "confidence": None,
        "citations": [],
        "grounding": {
            "quotes_requested": 0,
            "quotes_grounded": 0,
            "citations_emitted": 0,
            "citations_truncated": 0,
            "cross_segment_citations": 0,
        },
        "_model_quotes": [],
    }


def finalize_outcome_and_strip(
    answers: list[dict[str, Any]],
    *,
    empty: bool,
) -> tuple[list[dict[str, Any]], str]:
    outcome = compute_outcome(answers, empty=empty)
    cleaned: list[dict[str, Any]] = []
    for row in answers:
        out = {k: v for k, v in row.items() if not k.startswith("_")}
        cleaned.append(out)
    return cleaned, outcome


def build_llm_custom_qa_cache_key(
    *,
    questions_hash: str,
    transcript_fingerprint: str,
    bounded_input_fingerprint: str,
    model: str,
    generation_options: dict[str, Any],
    llm_request_sha256: str,
    template_hash: str,
    prompt_version: str = PROMPT_VERSION,
    schema_id: str = SCHEMA_ID,
    module_version: str = MODULE_VERSION,
    absence_detector_version: str = ABSENCE_DETECTOR_VERSION,
) -> str:
    payload = {
        "absence_detector_version": absence_detector_version,
        "bounded_input_fingerprint": bounded_input_fingerprint,
        "generation_options": dict(sorted(generation_options.items())),
        "llm_request_sha256": llm_request_sha256,
        "model": model,
        "module_version": module_version,
        "prompt_version": prompt_version,
        "questions_hash": questions_hash,
        "schema_id": schema_id,
        "template_hash": template_hash,
        "transcript_fingerprint": transcript_fingerprint,
    }
    return sha256_canonical_json(payload)
