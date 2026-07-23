"""Expanded offline coverage for llm_custom_qa critical paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.analysis.aggregation.llm import aggregate_llm_custom_qa_group
from transcriptx.core.analysis.llm_custom_qa.absence import apply_absence_detector
from transcriptx.core.analysis.llm_custom_qa.artifact_schema import (
    compute_outcome,
    empty_diagnostics,
    validate_artifact,
)
from transcriptx.core.analysis.llm_custom_qa.bounded_input import build_grounding_corpus
from transcriptx.core.analysis.llm_custom_qa.cache import try_load_cached_artifact
from transcriptx.core.analysis.llm_custom_qa.commit import (
    analytical_artifacts_readable,
    commit_llm_custom_qa_artifacts,
)
from transcriptx.core.analysis.llm_custom_qa.contract import (
    build_llm_custom_qa_cache_key,
    finalize_outcome_and_strip,
    process_raw_answers,
)
from transcriptx.core.analysis.llm_custom_qa.errors import (
    CustomQAError,
    CustomQAFailureCode,
    CustomQAModelResponseInvalidError,
    CustomQAQuestionsValidationError,
)
from transcriptx.core.analysis.llm_custom_qa.gating import consumer_requires_live_llm
from transcriptx.core.analysis.llm_custom_qa.grounding import (
    apply_grounding,
    ground_answered_row,
)
from transcriptx.core.analysis.llm_custom_qa.model_schema import parse_model_envelope
from transcriptx.core.analysis.llm_custom_qa.normalize import normalize_questions
from transcriptx.core.analysis.llm_custom_qa.questions_binding import (
    bind_custom_qa_questions,
    get_bound_custom_qa_questions,
    reset_custom_qa_questions,
)
from transcriptx.core.analysis.llm_custom_qa.readers import (
    find_committed_custom_qa_artifact,
)
from transcriptx.core.analysis.llm_custom_qa.render import render_custom_qa_markdown
from transcriptx.core.analysis.llm_custom_qa.resolve import (
    EffectiveCustomQAQuestions,
    normalize_library_questions,
    resolve_effective_custom_qa_questions,
    resolve_from_mapping,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


class _Settings:
    saved_questions = ["Library question one?", "Library question two?"]
    max_questions_per_run = 8
    max_question_chars = 500
    max_run_total_question_chars = 4000
    max_answer_chars = 800
    max_library_questions = 50
    max_library_total_question_chars = 20000


def _answered_raw(index: int, answer: str, *, quotes: list[str] | None = None) -> dict:
    return {
        "question_index": index,
        "status": "answered",
        "answer": answer,
        "abstain_reason": None,
        "confidence": 0.8,
        "quotes": quotes if quotes is not None else [],
    }


def _abstain_raw(index: int, reason: str = "insufficient_evidence") -> dict:
    return {
        "question_index": index,
        "status": "abstained",
        "answer": None,
        "abstain_reason": reason,
        "confidence": 0.2,
        "quotes": [],
    }


@pytest.mark.unit
def test_normalize_collapses_whitespace_and_dedupes_casefold() -> None:
    out = normalize_questions(
        ["  Hello\nworld  ", "hello WORLD", "\t", "Keep me"],
        max_questions=8,
        max_question_chars=500,
        max_total_question_chars=4000,
    )
    assert out == ("Hello world", "Keep me")


@pytest.mark.unit
def test_normalize_rejects_non_str_and_oversize() -> None:
    with pytest.raises(CustomQAQuestionsValidationError):
        normalize_questions(
            ["ok", 3],
            max_questions=8,
            max_question_chars=500,
            max_total_question_chars=4000,
        )
    with pytest.raises(CustomQAQuestionsValidationError):
        normalize_questions(
            ["x" * 10],
            max_questions=8,
            max_question_chars=5,
            max_total_question_chars=4000,
        )
    with pytest.raises(CustomQAQuestionsValidationError):
        normalize_questions(
            ["one", "two", "three"],
            max_questions=2,
            max_question_chars=500,
            max_total_question_chars=4000,
        )


@pytest.mark.unit
def test_resolve_request_and_from_mapping() -> None:
    # Case-sensitive identity: differing case is two questions
    effective = resolve_effective_custom_qa_questions(
        request_questions=["  What next?  ", "What next?"],
        request_field_present=True,
        settings=_Settings(),
    )
    assert effective.resolved_from == "request"
    assert effective.questions == ("What next?",)
    assert effective.empty is False
    assert consumer_requires_live_llm("llm_custom_qa", effective) is True

    via_map = resolve_from_mapping(
        {"llm_custom_qa_questions": ["Mapped Q?"]},
        settings=_Settings(),
    )
    assert via_map.resolved_from == "request"
    assert via_map.questions == ("Mapped Q?",)

    omitted = resolve_from_mapping({}, settings=_Settings())
    assert omitted.resolved_from == "library"
    assert omitted.questions[0].startswith("Library")


@pytest.mark.unit
def test_normalize_library_uses_library_limits() -> None:
    settings = _Settings()
    settings.max_library_questions = 2
    out = normalize_library_questions(["A?", "B?"], settings=settings)
    assert [q["text"] for q in out] == ["A?", "B?"]
    with pytest.raises(CustomQAQuestionsValidationError):
        normalize_library_questions(["A?", "B?", "C?"], settings=settings)


@pytest.mark.unit
def test_envelope_top_level_failures() -> None:
    with pytest.raises(CustomQAModelResponseInvalidError) as inv:
        parse_model_envelope("{not-json")
    assert inv.value.code == CustomQAFailureCode.CUSTOM_QA_MODEL_RESPONSE_INVALID

    with pytest.raises(CustomQAModelResponseInvalidError):
        parse_model_envelope([1, 2, 3])

    with pytest.raises(CustomQAModelResponseInvalidError):
        parse_model_envelope({"no_answers": []})

    with pytest.raises(CustomQAModelResponseInvalidError):
        parse_model_envelope({"answers": {"0": {}}})

    with pytest.raises(CustomQAModelResponseInvalidError):
        parse_model_envelope({"answers": [], "extra": True})


@pytest.mark.unit
def test_two_pass_oversize_invalid_incomplete_and_first_valid_wins() -> None:
    questions = ["Q0", "Q1", "Q2"]
    oversize = "y" * 900
    raw = [
        {"question_index": 0, "status": "answered", "bad": True},  # invalid candidate
        _answered_raw(0, "Recovered"),  # first valid wins
        _answered_raw(1, oversize),  # over-limit → invalid
        {"not_an_index": True},  # unidentifiable drop
        # Q2 missing → incomplete
    ]
    rows, diag = process_raw_answers(
        raw, questions_requested=questions, max_answer_chars=800
    )
    assert rows[0]["status"] == "answered"
    assert rows[0]["answer"] == "Recovered"
    assert rows[1]["status"] == "unavailable"
    assert rows[1]["system_reason"] == "response_invalid"
    assert rows[2]["status"] == "unavailable"
    assert rows[2]["system_reason"] == "response_incomplete"
    assert diag["answers_over_limit"] == 1
    assert diag["response_invalid_count"] == 1
    assert diag["response_incomplete_count"] == 1
    assert diag["extra_or_duplicate_rows_dropped"] >= 1


@pytest.mark.unit
def test_compute_outcome_variants_and_finalize_strips_private() -> None:
    assert compute_outcome([], empty=True) == "empty_questions"
    assert (
        compute_outcome([{"status": "answered"}, {"status": "answered"}], empty=False)
        == "answered"
    )
    assert (
        compute_outcome(
            [{"status": "abstained"}, {"status": "abstained"}], empty=False
        )
        == "all_abstained"
    )
    assert (
        compute_outcome(
            [{"status": "unavailable"}, {"status": "unavailable"}], empty=False
        )
        == "all_unavailable"
    )
    assert (
        compute_outcome(
            [{"status": "answered"}, {"status": "abstained"}], empty=False
        )
        == "mixed"
    )
    cleaned, outcome = finalize_outcome_and_strip(
        [
            {
                "question_index": 0,
                "question": "Q",
                "status": "answered",
                "answer": "A",
                "_model_quotes": ["x"],
            }
        ],
        empty=False,
    )
    assert outcome == "answered"
    assert "_model_quotes" not in cleaned[0]


@pytest.mark.unit
def test_grounding_corpus_prefer_tail_keeps_meeting_end() -> None:
    segments = [
        {"text": "AAAA", "start": 0.0, "end": 1.0},
        {"text": "BBBB", "start": 1.0, "end": 2.0},
        {"text": "CCCC", "start": 2.0, "end": 3.0},
        {"text": "DDDD", "start": 3.0, "end": 4.0},
    ]
    # Full corpus is "AAAA\nBBBB\nCCCC\nDDDD" (19 chars). Cap forces truncation.
    head = build_grounding_corpus(segments, max_corpus_chars=9, prefer="head")
    tail = build_grounding_corpus(segments, max_corpus_chars=9, prefer="tail")
    assert head.truncated and tail.truncated
    assert head.corpus_text.startswith("AAAA")
    assert "DDDD" not in head.corpus_text
    assert tail.corpus_text.endswith("DDDD")
    assert not tail.corpus_text.startswith("AAAA")
    # Tail window should include the newest original index.
    assert tail.entries[-1].original_segment_index == 3


@pytest.mark.unit
def test_grounding_corpus_tail_partial_cuts_oldest_kept_segment() -> None:
    segments = [
        {"text": "ABCDEFGH", "start": 0.0, "end": 1.0},
        {"text": "XYZ", "start": 1.0, "end": 2.0},
    ]
    # Keep "XYZ" (3) + sep (1) + suffix of first segment.
    corpus = build_grounding_corpus(segments, max_corpus_chars=7, prefer="tail")
    assert corpus.truncated
    assert corpus.partial_final_segment
    assert corpus.corpus_text.endswith("XYZ")
    assert corpus.entries[-1].text == "XYZ"
    assert "XYZ" in corpus.corpus_text
    # Oldest kept text is a suffix of ABCDEFGH.
    assert "ABCDEFGH".endswith(corpus.entries[0].text)


@pytest.mark.unit
def test_quality_retry_helpers_detect_and_describe_failures() -> None:
    from transcriptx.core.analysis.llm_custom_qa.analyze import (
        _build_repair_user_prompt,
        _needs_quality_retry,
        _system_prompt,
    )

    assert not _needs_quality_retry(empty_diagnostics())
    assert _needs_quality_retry({**empty_diagnostics(), "response_incomplete_count": 1})
    assert _needs_quality_retry({**empty_diagnostics(), "grounding_failed_count": 2})

    prompt = _system_prompt(question_count=2)
    assert "exactly 2 answer objects" in prompt
    assert "0 through 1" in prompt
    assert "never paraphrase" in prompt

    repair = _build_repair_user_prompt(
        base_user_prompt="BASE",
        answers=[
            {
                "question_index": 0,
                "status": "unavailable",
                "system_reason": "grounding_failed",
            },
            {
                "question_index": 1,
                "status": "unavailable",
                "system_reason": "response_incomplete",
            },
        ],
        question_count=2,
    )
    assert repair.startswith("BASE")
    assert "<<<REPAIR>>>" in repair
    assert "question_index 0: grounding_failed" in repair
    assert "question_index 1: response_incomplete" in repair


@pytest.mark.unit
def test_grounding_recovers_longest_interior_word_span() -> None:
    segments = [
        {
            "text": "it doesn't actually mean we're doing a bad job.",
            "start": 0.0,
            "end": 1.0,
        }
    ]
    corpus = build_grounding_corpus(segments, max_corpus_chars=10_000)
    paraphrased = (
        "I don't know, like I just think we've done really well and it's not "
        "perfect but it doesn't actually mean we're doing a bad job."
    )
    out = ground_answered_row(
        {
            "question_index": 0,
            "question": "q",
            "status": "answered",
            "answer": "aligned",
            "confidence": 0.9,
            "_model_quotes": [paraphrased],
        },
        corpus,
    )
    assert out["status"] == "answered"
    assert out["citations"]
    assert "doesn't actually mean we're doing a bad job" in out["citations"][0]["quote"]


@pytest.mark.unit
def test_grounding_failed_and_citation_cap() -> None:
    segments = [
        {"text": "alpha one", "start": 0.0, "end": 1.0},
        {"text": "beta two", "start": 1.0, "end": 2.0},
        {"text": "gamma three", "start": 2.0, "end": 3.0},
    ]
    corpus = build_grounding_corpus(segments, max_corpus_chars=10_000)
    failed = ground_answered_row(
        {
            "question_index": 0,
            "question": "q",
            "status": "answered",
            "answer": "nope",
            "confidence": 0.5,
            "_model_quotes": ["this quote is not in the corpus"],
        },
        corpus,
    )
    assert failed["status"] == "unavailable"
    assert failed["system_reason"] == "grounding_failed"

    many_quotes = [
        "alpha one",
        "beta two",
        "gamma three",
        "alpha one",  # duplicate / extra beyond cap
    ]
    row = {
        "question_index": 0,
        "question": "q",
        "status": "answered",
        "answer": "all",
        "confidence": 0.9,
        "_model_quotes": many_quotes,
    }
    grounded = ground_answered_row(row, corpus, max_citations=2)
    assert grounded["status"] == "answered"
    assert len(grounded["citations"]) == 2
    assert grounded["grounding"]["citations_truncated"] >= 1

    diag = empty_diagnostics()
    apply_grounding([row], corpus, diagnostics=diag)
    assert diag["citations_total"] >= 1


@pytest.mark.unit
def test_absence_detector_counts_only_when_truncated() -> None:
    answers = [
        {
            "question_index": 0,
            "question": "Q",
            "status": "abstained",
            "abstain_reason": "not_in_provided_excerpt",
            "answer": None,
        }
    ]
    diag = empty_diagnostics()
    unchanged = apply_absence_detector(answers, truncated=False, diagnostics=diag)
    assert unchanged[0]["status"] == "abstained"
    assert diag["absence_detector_hits"] == 0

    apply_absence_detector(answers, truncated=True, diagnostics=diag)
    assert diag["absence_detector_hits"] == 1


@pytest.mark.unit
def test_cache_key_sorted_generation_options_stable() -> None:
    a = build_llm_custom_qa_cache_key(
        questions_hash="qh",
        transcript_fingerprint="tf",
        bounded_input_fingerprint="bf",
        model="m",
        generation_options={"temperature": 0.0, "seed": 1},
        llm_request_sha256="req",
        template_hash="th",
    )
    b = build_llm_custom_qa_cache_key(
        questions_hash="qh",
        transcript_fingerprint="tf",
        bounded_input_fingerprint="bf",
        model="m",
        generation_options={"seed": 1, "temperature": 0.0},
        llm_request_sha256="req",
        template_hash="th",
    )
    assert a == b
    c = build_llm_custom_qa_cache_key(
        questions_hash="qh",
        transcript_fingerprint="tf",
        bounded_input_fingerprint="bf",
        model="m",
        generation_options={"seed": 2, "temperature": 0.0},
        llm_request_sha256="req",
        template_hash="th",
    )
    assert a != c


@pytest.mark.unit
def test_cache_miss_on_key_or_hash_mismatch(tmp_path: Path) -> None:
    from transcriptx.core.analysis.llm_custom_qa.analyze import _empty_run_payload

    effective = resolve_effective_custom_qa_questions(
        request_questions=[], request_field_present=True, settings=_Settings()
    )
    payload = validate_artifact(_empty_run_payload(effective))
    payload["cache_key"] = "wanted"
    payload["provenance"]["cache_key"] = "wanted"
    path = tmp_path / "x_llm_custom_qa.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert (
        try_load_cached_artifact(
            path,
            cache_key="other",
            questions_requested=[],
            questions_hash=effective.questions_hash,
        )
        is None
    )
    with pytest.raises(CustomQAError) as exc:
        try_load_cached_artifact(
            path,
            cache_key="wanted",
            questions_requested=[],
            questions_hash="wrong-hash",
        )
    assert exc.value.code == CustomQAFailureCode.CUSTOM_QA_CACHE_INVALID


@pytest.mark.unit
def test_questions_binding_contextvar_roundtrip() -> None:
    effective = resolve_effective_custom_qa_questions(
        request_questions=["Bound?"],
        request_field_present=True,
        settings=_Settings(),
    )
    assert get_bound_custom_qa_questions() is None
    token = bind_custom_qa_questions(effective)
    try:
        bound = get_bound_custom_qa_questions()
        assert bound is not None
        assert bound.questions == ("Bound?",)
        assert bound.questions_hash == effective.questions_hash
    finally:
        reset_custom_qa_questions(token)
    assert get_bound_custom_qa_questions() is None


@pytest.mark.unit
def test_render_markdown_covers_row_statuses() -> None:
    md = render_custom_qa_markdown(
        {
            "questions_requested": ["A?", "B?", "C?"],
            "outcome": "mixed",
            "answers": [
                {
                    "question_index": 0,
                    "question": "A?",
                    "status": "answered",
                    "answer": "Yes",
                    "citations": [
                        {
                            "quote": "hello\nworld",
                            "segment_indexes": [0],
                        }
                    ],
                },
                {
                    "question_index": 1,
                    "question": "B?",
                    "status": "abstained",
                    "abstain_reason": "ambiguous",
                },
                {
                    "question_index": 2,
                    "question": "C?",
                    "status": "unavailable",
                    "system_reason": "response_incomplete",
                },
            ],
        }
    )
    assert "Outcome: `mixed`" in md
    assert "Status: `answered`" in md
    assert "hello / world" in md
    assert "Abstain reason: `ambiguous`" in md
    assert "System reason: `response_incomplete`" in md


@pytest.mark.unit
def test_reader_rejects_failed_module_even_with_commit(tmp_path: Path) -> None:
    from transcriptx.core.analysis.llm_custom_qa.analyze import _empty_run_payload

    effective = resolve_effective_custom_qa_questions(
        request_questions=[], request_field_present=True, settings=_Settings()
    )
    payload = validate_artifact(_empty_run_payload(effective))
    stem = tmp_path / "demo_llm_custom_qa"
    commit_llm_custom_qa_artifacts(
        stem=stem,
        json_final=Path(f"{stem}.json"),
        md_final=Path(f"{stem}.md"),
        payload=payload,
        markdown="# empty\n",
    )
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "modules_run": [],
                "modules_failed": ["llm_custom_qa"],
            }
        ),
        encoding="utf-8",
    )
    assert find_committed_custom_qa_artifact(tmp_path) is None
    assert analytical_artifacts_readable(stem=stem, module_succeeded=False) is False


@pytest.mark.unit
def test_group_aggregation_rows_and_hash_mismatch() -> None:
    def _ts() -> TranscriptSet:
        return TranscriptSet.create(
            ["/x/a.json", "/x/b.json", "/x/c.json"], name="G", key="gk"
        )

    def _cmap() -> CanonicalSpeakerMap:
        return CanonicalSpeakerMap(
            transcript_to_speakers={
                "/x/a.json": {"1": 7},
                "/x/b.json": {"1": 7},
                "/x/c.json": {"1": 7},
            },
            canonical_to_display={7: "Alice"},
            transcript_to_display={
                "/x/a.json": {"1": "Alice"},
                "/x/b.json": {"1": "Alice"},
                "/x/c.json": {"1": "Alice"},
            },
        )

    def _result(
        path: str,
        key: str,
        order: int,
        *,
        status: str,
        payload: dict | None,
        output_dir: str = "o1",
    ) -> PerTranscriptResult:
        module: dict = {"status": status}
        if payload is not None:
            module["payload"] = payload
        return PerTranscriptResult(
            transcript_path=path,
            transcript_key=key,
            run_id=f"r{order}",
            order_index=order,
            output_dir=output_dir,
            module_results={"llm_custom_qa": module},
        )

    shared = {
        "schema_id": "transcriptx.llm_custom_qa.v1",
        "questions_hash": "hash-a",
        "questions_requested": ["Q?"],
        "outcome": "answered",
        "provenance": {"resolved_from": "request"},
        "answers": [
            {
                "question_index": 0,
                "question": "Q?",
                "status": "answered",
                "answer": "Because",
                "abstain_reason": None,
                "system_reason": None,
                "confidence": 0.7,
                "citations": [],
            }
        ],
    }
    mismatched = dict(shared)
    mismatched["questions_hash"] = "hash-b"

    results = [
        _result("/x/a.json", "a", 0, status="success", payload=shared),
        _result(
            "/x/b.json",
            "b",
            1,
            status="failed",
            payload=None,
            output_dir="o2",
        ),
        _result(
            "/x/c.json",
            "c",
            2,
            status="success",
            payload=mismatched,
            output_dir="o3",
        ),
    ]
    out = aggregate_llm_custom_qa_group(results, _cmap(), _ts())
    assert out is not None
    assert out["content_rows_name"] == "qa_answer_rows"
    assert len(out["content_rows"]) == 1
    assert out["content_rows"][0]["answer"] == "Because"
    assert out["group_metadata"]["questions_hash"] == "hash-a"
    assert out["group_metadata"]["resolved_from"] == "request"
    reasons = {f["reason"] for f in out["extra_tables"]["qa_member_failures"]}
    assert "module_not_success" in reasons
    assert "hash_or_schema_mismatch" in reasons


@pytest.mark.unit
def test_effective_metadata_export() -> None:
    effective = EffectiveCustomQAQuestions(
        questions=("Only?",),
        questions_hash="abc",
        empty=False,
        resolved_from="request",
        max_questions_per_run=8,
        max_question_chars=500,
        max_run_total_question_chars=4000,
        max_answer_chars=800,
    )
    meta = effective.to_metadata()
    assert meta["questions_requested"] == ["Only?"]
    assert meta["questions_hash"] == "abc"
    assert meta["resolved_from"] == "request"
    assert meta["question_order"] == []
    assert meta["structured"] == []
