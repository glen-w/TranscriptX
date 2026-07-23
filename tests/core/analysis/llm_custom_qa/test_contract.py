"""Contract tests for llm_custom_qa frozen schemas and algorithms."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.analysis.llm_custom_qa.artifact_schema import (
    validate_artifact,
)
from transcriptx.core.analysis.llm_custom_qa.bounded_input import build_grounding_corpus
from transcriptx.core.analysis.llm_custom_qa.commit import (
    analytical_artifacts_readable,
    commit_llm_custom_qa_artifacts,
    read_active_generation_id,
)
from transcriptx.core.analysis.llm_custom_qa.constants import GROUNDING_SEGMENT_SEPARATOR
from transcriptx.core.analysis.llm_custom_qa.contract import process_raw_answers
from transcriptx.core.analysis.llm_custom_qa.errors import (
    CustomQAFailureCode,
    CustomQAQuestionsValidationError,
    map_exception_to_failure_code,
)
from transcriptx.core.analysis.llm_custom_qa.gating import consumer_requires_live_llm
from transcriptx.core.analysis.llm_custom_qa.grounding import ground_answered_row
from transcriptx.core.analysis.llm_custom_qa.model_schema import (
    parse_model_envelope,
    try_parse_answer_row,
)
from transcriptx.core.analysis.llm_custom_qa.normalize import normalize_questions
from transcriptx.core.analysis.llm_custom_qa.resolve import (
    EffectiveCustomQAQuestions,
    resolve_effective_custom_qa_questions,
)


class _Settings:
    saved_questions = ["What was decided?", "Who owns follow-up?"]
    max_questions_per_run = 8
    max_question_chars = 500
    max_run_total_question_chars = 4000
    max_answer_chars = 800
    max_library_questions = 50
    max_library_total_question_chars = 20000


def test_normalize_rejects_scalar_str_and_bytes() -> None:
    with pytest.raises(CustomQAQuestionsValidationError):
        normalize_questions(
            "not a list",
            max_questions=8,
            max_question_chars=500,
            max_total_question_chars=4000,
        )
    with pytest.raises(CustomQAQuestionsValidationError):
        normalize_questions(
            b"bytes",
            max_questions=8,
            max_question_chars=500,
            max_total_question_chars=4000,
        )


def test_resolve_explicit_empty() -> None:
    effective = resolve_effective_custom_qa_questions(
        request_questions=[],
        request_field_present=True,
        settings=_Settings(),
    )
    assert effective.resolved_from == "explicit_empty"
    assert effective.empty
    assert effective.questions == ()


def test_resolve_omit_and_null_are_library() -> None:
    a = resolve_effective_custom_qa_questions(
        request_questions=None,
        request_field_present=False,
        settings=_Settings(),
    )
    b = resolve_effective_custom_qa_questions(
        request_questions=None,
        request_field_present=True,
        settings=_Settings(),
    )
    assert a.resolved_from == "library"
    assert b.resolved_from == "library"
    assert a.questions == b.questions


def test_envelope_accepts_mixed_rows() -> None:
    raw = {
        "answers": [
            {
                "question_index": 0,
                "status": "answered",
                "answer": "Yes",
                "abstain_reason": None,
                "confidence": 0.9,
                "quotes": ["hello world"],
            },
            {"bad": True},
            {
                "question_index": 1,
                "status": "abstained",
                "answer": None,
                "abstain_reason": "insufficient_evidence",
                "confidence": 0,
                "quotes": [],
            },
        ]
    }
    answers = parse_model_envelope(raw)
    assert len(answers) == 3
    rows, diag = process_raw_answers(
        answers,
        questions_requested=["Q0", "Q1"],
        max_answer_chars=800,
    )
    assert rows[0]["status"] == "answered"
    assert rows[1]["status"] == "abstained"
    assert diag["extra_or_duplicate_rows_dropped"] >= 1


def test_confidence_int_ok_bool_rejected() -> None:
    ok = try_parse_answer_row(
        {
            "question_index": 0,
            "status": "abstained",
            "answer": None,
            "abstain_reason": "ambiguous",
            "confidence": 1,
            "quotes": [],
        }
    )
    assert ok is not None
    bad = try_parse_answer_row(
        {
            "question_index": 0,
            "status": "abstained",
            "answer": None,
            "abstain_reason": "ambiguous",
            "confidence": True,
            "quotes": [],
        }
    )
    assert bad is None


def test_cross_segment_citation_quote_contains_separator() -> None:
    segments = [
        {"text": "alpha one", "start": 0.0, "end": 1.0},
        {"text": "beta two", "start": 1.0, "end": 2.0},
    ]
    corpus = build_grounding_corpus(segments, max_corpus_chars=10_000)
    assert GROUNDING_SEGMENT_SEPARATOR in corpus.corpus_text
    row = {
        "question_index": 0,
        "question": "q",
        "status": "answered",
        "answer": "both",
        "confidence": 0.5,
        "_model_quotes": [corpus.corpus_text],
    }
    grounded = ground_answered_row(row, corpus)
    assert grounded["status"] == "answered"
    assert grounded["citations"]
    assert GROUNDING_SEGMENT_SEPARATOR in grounded["citations"][0]["quote"]


def test_commit_marker_protocol(tmp_path: Path) -> None:
    stem = tmp_path / "demo_llm_custom_qa"
    json_final = Path(f"{stem}.json")
    md_final = Path(f"{stem}.md")
    settings = _Settings()
    effective = resolve_effective_custom_qa_questions(
        request_questions=[],
        request_field_present=True,
        settings=settings,
    )
    from transcriptx.core.analysis.llm_custom_qa.analyze import _empty_run_payload

    payload = validate_artifact(_empty_run_payload(effective))
    gid = commit_llm_custom_qa_artifacts(
        stem=stem,
        json_final=json_final,
        md_final=md_final,
        payload=payload,
        markdown="# empty\n",
    )
    assert read_active_generation_id(stem) == gid
    assert analytical_artifacts_readable(stem=stem, module_succeeded=True)
    assert not analytical_artifacts_readable(stem=stem, module_succeeded=False)


def test_empty_run_coverage_ratio_null() -> None:
    from transcriptx.core.analysis.llm_custom_qa.analyze import _empty_run_payload

    payload = validate_artifact(_empty_run_payload(
        resolve_effective_custom_qa_questions(
            request_questions=[],
            request_field_present=True,
            settings=_Settings(),
        )
    ))
    assert payload["input_coverage"]["input_coverage_ratio"] is None
    assert payload["cache_key"] is None
    assert payload["provenance"]["cache_key"] is None
    assert payload["provenance"]["provider"] is None


def test_consumer_gate_empty_skips_live_llm() -> None:
    effective = EffectiveCustomQAQuestions(
        questions=(),
        questions_hash="x",
        empty=True,
        resolved_from="explicit_empty",
        max_questions_per_run=8,
        max_question_chars=500,
        max_run_total_question_chars=4000,
        max_answer_chars=800,
    )
    assert consumer_requires_live_llm("llm_custom_qa", effective) is False
    assert consumer_requires_live_llm("llm_action_items", effective) is True


def test_failure_code_mapping_table() -> None:
    assert (
        map_exception_to_failure_code(TimeoutError("timed out"))
        == CustomQAFailureCode.CUSTOM_QA_TIMEOUT
    )
    assert (
        map_exception_to_failure_code(RuntimeError("provider unreachable"))
        == CustomQAFailureCode.CUSTOM_QA_PROVIDER_UNAVAILABLE
    )


def test_golden_empty_artifact_shape() -> None:
    from transcriptx.core.analysis.llm_custom_qa.analyze import _empty_run_payload

    payload = validate_artifact(
        _empty_run_payload(
            resolve_effective_custom_qa_questions(
                request_questions=[],
                request_field_present=True,
                settings=_Settings(),
            )
        )
    )
    golden_dir = Path(__file__).parent / "goldens"
    golden_dir.mkdir(exist_ok=True)
    path = golden_dir / "empty_run_artifact.json"
    if not path.exists():
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    expected = json.loads(path.read_text(encoding="utf-8"))
    # questions_hash depends on empty list — stable
    assert payload["questions_hash"] == expected["questions_hash"]
    assert payload["outcome"] == "empty_questions"
