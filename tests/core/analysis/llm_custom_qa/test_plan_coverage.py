"""Extra §12 coverage: failure codes, cache reuse, readers, fuzz normalize."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from transcriptx.core.analysis.llm_custom_qa.cache import try_load_cached_artifact
from transcriptx.core.analysis.llm_custom_qa.commit import (
    commit_llm_custom_qa_artifacts,
)
from transcriptx.core.analysis.llm_custom_qa.errors import (
    CustomQAError,
    CustomQAFailureCode,
    CustomQAModelResponseInvalidError,
    CustomQAQuestionsValidationError,
    map_exception_to_failure_code,
)
from transcriptx.core.analysis.llm_custom_qa.normalize import normalize_questions
from transcriptx.core.analysis.llm_custom_qa.readers import (
    find_committed_custom_qa_artifact,
    load_committed_custom_qa_payload,
)
from transcriptx.core.config.persistence import (
    ConfigCorruptError,
    ConfigLockTimeoutError,
)


def test_failure_code_mapping_table_complete() -> None:
    """Every §11 code is representable; common exceptions map uniquely."""
    assert {c.value for c in CustomQAFailureCode} == {
        "CUSTOM_QA_QUESTIONS_INVALID",
        "CUSTOM_QA_EMPTY_INPUT",
        "CUSTOM_QA_MODEL_RESPONSE_INVALID",
        "CUSTOM_QA_PROVIDER_UNAVAILABLE",
        "CUSTOM_QA_MODEL_MISSING",
        "CUSTOM_QA_TIMEOUT",
        "CUSTOM_QA_CANCELLED",
        "CUSTOM_QA_CLIENT_ERROR",
        "CUSTOM_QA_RETRY_EXHAUSTED",
        "CUSTOM_QA_ARTIFACT_VALIDATION_FAILED",
        "CUSTOM_QA_ARTIFACT_COMMIT_FAILED",
        "CUSTOM_QA_CACHE_INVALID",
        "CONFIG_LOCK_TIMEOUT",
        "CONFIG_CORRUPT",
        "CUSTOM_QA_INTERNAL",
    }
    cases = [
        (CustomQAQuestionsValidationError("bad"), CustomQAFailureCode.CUSTOM_QA_QUESTIONS_INVALID),
        (
            CustomQAModelResponseInvalidError("bad json"),
            CustomQAFailureCode.CUSTOM_QA_MODEL_RESPONSE_INVALID,
        ),
        (TimeoutError("timed out"), CustomQAFailureCode.CUSTOM_QA_TIMEOUT),
        (RuntimeError("cancelled by user"), CustomQAFailureCode.CUSTOM_QA_CANCELLED),
        (RuntimeError("provider unreachable"), CustomQAFailureCode.CUSTOM_QA_PROVIDER_UNAVAILABLE),
        (RuntimeError("model not found"), CustomQAFailureCode.CUSTOM_QA_MODEL_MISSING),
        (RuntimeError("unauthorized"), CustomQAFailureCode.CUSTOM_QA_CLIENT_ERROR),
        (ConfigLockTimeoutError(), CustomQAFailureCode.CONFIG_LOCK_TIMEOUT),
        (ConfigCorruptError(), CustomQAFailureCode.CONFIG_CORRUPT),
        (RuntimeError("mystery"), CustomQAFailureCode.CUSTOM_QA_INTERNAL),
    ]
    for exc, expected in cases:
        assert map_exception_to_failure_code(exc) == expected


def test_cache_validate_before_reuse(tmp_path: Path) -> None:
    from transcriptx.core.analysis.llm_custom_qa.analyze import _empty_run_payload
    from transcriptx.core.analysis.llm_custom_qa.artifact_schema import validate_artifact
    from transcriptx.core.analysis.llm_custom_qa.resolve import (
        resolve_effective_custom_qa_questions,
    )

    class S:
        saved_questions = []
        max_questions_per_run = 8
        max_question_chars = 500
        max_run_total_question_chars = 4000
        max_answer_chars = 800
        max_library_questions = 50
        max_library_total_question_chars = 20000

    effective = resolve_effective_custom_qa_questions(
        request_questions=[], request_field_present=True, settings=S()
    )
    payload = validate_artifact(_empty_run_payload(effective))
    # Empty-run cache_key is null — craft a non-empty cache key artifact
    payload["cache_key"] = "abc"
    payload["provenance"]["cache_key"] = "abc"
    json_final = tmp_path / "x_llm_custom_qa.json"
    json_final.write_text(json.dumps(payload), encoding="utf-8")
    hit = try_load_cached_artifact(
        json_final,
        cache_key="abc",
        questions_requested=[],
        questions_hash=effective.questions_hash,
    )
    assert hit is not None
    with pytest.raises(CustomQAError) as exc:
        # Corrupt answers length to force validation failure
        bad = dict(payload)
        bad["answers"] = [{"question_index": 0}]
        json_final.write_text(json.dumps(bad), encoding="utf-8")
        try_load_cached_artifact(
            json_final,
            cache_key="abc",
            questions_requested=[],
            questions_hash=effective.questions_hash,
        )
    assert exc.value.code == CustomQAFailureCode.CUSTOM_QA_CACHE_INVALID


def test_reader_requires_run_results_success(tmp_path: Path) -> None:
    from transcriptx.core.analysis.llm_custom_qa.analyze import _empty_run_payload
    from transcriptx.core.analysis.llm_custom_qa.artifact_schema import validate_artifact
    from transcriptx.core.analysis.llm_custom_qa.resolve import (
        resolve_effective_custom_qa_questions,
    )

    class S:
        saved_questions = []
        max_questions_per_run = 8
        max_question_chars = 500
        max_run_total_question_chars = 4000
        max_answer_chars = 800
        max_library_questions = 50
        max_library_total_question_chars = 20000

    effective = resolve_effective_custom_qa_questions(
        request_questions=[], request_field_present=True, settings=S()
    )
    payload = validate_artifact(_empty_run_payload(effective))
    stem = tmp_path / "demo_llm_custom_qa"
    json_final = Path(f"{stem}.json")
    md_final = Path(f"{stem}.md")
    commit_llm_custom_qa_artifacts(
        stem=stem,
        json_final=json_final,
        md_final=md_final,
        payload=payload,
        markdown="# empty\n",
    )
    assert find_committed_custom_qa_artifact(tmp_path) is None
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "r",
                "transcript_key": "t",
                "modules_enabled": ["llm_custom_qa"],
                "modules_run": ["llm_custom_qa"],
                "modules_skipped": [],
                "modules_failed": [],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    assert find_committed_custom_qa_artifact(tmp_path) == json_final
    assert load_committed_custom_qa_payload(tmp_path) is not None


@given(st.lists(st.text(min_size=1, max_size=40), min_size=0, max_size=5))
@settings(max_examples=40, deadline=None)
def test_normalize_property_dedupe_and_limits(raw: list[str]) -> None:
    try:
        out = normalize_questions(
            raw,
            max_questions=8,
            max_question_chars=500,
            max_total_question_chars=4000,
        )
    except CustomQAQuestionsValidationError:
        return
    assert len(out) == len({q.casefold() for q in out})
    assert all(isinstance(q, str) and q == q.strip() for q in out)


def test_max_answer_chars_parity_with_settings_model() -> None:
    from transcriptx.core.analysis.llm_custom_qa.constants import MAX_ANSWER_CHARS
    from transcriptx.core.config.models.llm_custom_qa import LLMCustomQASettingsModel

    assert MAX_ANSWER_CHARS == LLMCustomQASettingsModel().max_answer_chars == 800
