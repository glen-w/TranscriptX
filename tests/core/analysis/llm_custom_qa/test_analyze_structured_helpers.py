"""Offline unit coverage for llm_custom_qa analyze_structured helpers."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.llm_custom_qa.analyze_structured import (
    _empty_structured_payload,
    _is_retryable,
    _questions_requested_payload,
    _structured_system_prompt,
    _unavailable_cell,
)
from transcriptx.core.analysis.llm_custom_qa.errors import (
    CustomQAError,
    CustomQAFailureCode,
    CustomQAModelResponseInvalidError,
)
from transcriptx.core.analysis.llm_custom_qa.question_identity import (
    CanonicalQuestion,
    QuestionScopes,
)
from transcriptx.core.analysis.llm_custom_qa.resolve import EffectiveCustomQAQuestions
from transcriptx.core.analysis.llm_custom_qa.versioning import SCHEMA_ID


def _q(text: str = "Who decided?") -> CanonicalQuestion:
    return CanonicalQuestion(
        question_id="q_test",
        text=text,
        scopes=QuestionScopes(global_scope=True, per_speaker=False),
    )


def _effective(
    *, structured: tuple[CanonicalQuestion, ...] = ()
) -> EffectiveCustomQAQuestions:
    return EffectiveCustomQAQuestions(
        questions=tuple(q.text for q in structured) or (),
        questions_hash="hash",
        empty=not structured,
        resolved_from="explicit_empty" if not structured else "request",
        max_questions_per_run=8,
        max_question_chars=500,
        max_run_total_question_chars=4000,
        max_answer_chars=800,
        structured=structured,
        question_order=tuple(q.question_id for q in structured),
    )


@pytest.mark.unit
def test_structured_system_prompt_counts_questions() -> None:
    prompt = _structured_system_prompt(question_count=3)
    assert "exactly 3 answer objects" in prompt
    assert "0 through 2" in prompt
    assert _structured_system_prompt(question_count=0).count("0 through 0") == 1


@pytest.mark.unit
def test_questions_requested_payload_shape() -> None:
    q = _q()
    payload = _questions_requested_payload((q,))
    assert payload == [
        {
            "question_id": "q_test",
            "text": "Who decided?",
            "scopes": {"global": True, "per_speaker": False},
        }
    ]


@pytest.mark.unit
def test_empty_structured_payload_empty_and_structured() -> None:
    empty = _empty_structured_payload(_effective())
    assert empty["schema_id"] == SCHEMA_ID
    assert empty["outcome"] == "empty_questions"
    assert empty["answers"] == []
    assert empty["provenance"]["empty_run"] is True

    structured = _empty_structured_payload(_effective(structured=(_q(),)))
    assert structured["questions_requested"][0]["question_id"] == "q_test"
    assert structured["question_order"] == ["q_test"]
    assert structured["questions_hash"]


@pytest.mark.unit
def test_unavailable_cell_defaults() -> None:
    cell = _unavailable_cell(
        question=_q(),
        scope="global",
        speaker_key=None,
        system_reason="budget",
    )
    assert cell["status"] == "unavailable"
    assert cell["system_reason"] == "budget"
    assert cell["answer"] is None
    assert cell["evidence_used"]["use_transcript"] is False


@pytest.mark.unit
def test_is_retryable_classification() -> None:
    assert _is_retryable(CustomQAModelResponseInvalidError("bad")) is False
    assert (
        _is_retryable(
            CustomQAError(
                "timeout",
                code=CustomQAFailureCode.CUSTOM_QA_TIMEOUT,
            )
        )
        is True
    )
    assert _is_retryable(TimeoutError("timed out")) is True
    assert _is_retryable(RuntimeError("connection reset")) is True
    assert _is_retryable(ValueError("nope")) is False
