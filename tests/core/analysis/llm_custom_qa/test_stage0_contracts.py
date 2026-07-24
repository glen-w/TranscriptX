"""Stage 0: question identity, outcome truth table, contracts, versioning."""

from __future__ import annotations

import pytest

import transcriptx.core.analysis.llm_custom_qa.constants as custom_qa_constants
import transcriptx.core.analysis.llm_custom_qa.versioning as custom_qa_versioning
from transcriptx.core.analysis.llm_custom_qa.structured_contracts import compute_structured_outcome
from transcriptx.core.analysis.llm_custom_qa.errors import (
    CustomQAQuestionsValidationError,
)
from transcriptx.core.analysis.llm_custom_qa.question_identity import (
    canonicalize_questions,
    merge_evidence_pack_ids,
    normalize_question_text,
    question_id_for_text,
    questions_hash_for_canonical,
)
from transcriptx.core.analysis.llm_custom_qa.versioning import (
    COMMIT_MARKER_SCHEMA_VERSION,
    CONTRACT_VERSION,
    MODULE_VERSION,
    SCHEMA_ID,
    is_structured_execution_enabled,
    live_module_version_for_writers,
    live_schema_id_for_writers,
)


@pytest.mark.unit
def test_activation_defaults_to_live() -> None:
    """Sole live writer path; schema id is transcriptx.llm_custom_qa.v1."""
    assert is_structured_execution_enabled() is False
    assert SCHEMA_ID == "transcriptx.llm_custom_qa.v1"
    assert live_schema_id_for_writers() == SCHEMA_ID
    assert live_module_version_for_writers() == MODULE_VERSION


@pytest.mark.unit
def test_sole_identity_constants_no_dual_aliases() -> None:
    """Public identities are single symbols; dual V1_/V2_ aliases stay gone."""
    assert MODULE_VERSION == "1"
    assert CONTRACT_VERSION == "1"
    assert COMMIT_MARKER_SCHEMA_VERSION == 1
    removed = (
        "V1_SCHEMA_ID",
        "V2_SCHEMA_ID",
        "V1_MODULE_VERSION",
        "V2_MODULE_VERSION",
        "V1_CONTRACT_VERSION",
        "V2_CONTRACT_VERSION",
        "COMMIT_MARKER_SCHEMA_VERSION_V1",
        "COMMIT_MARKER_SCHEMA_VERSION_V2",
        "get_custom_qa_activation",
        "set_custom_qa_activation",
        "is_v2_execution_enabled",
        "CustomQAActivation",
    )
    for name in removed:
        assert not hasattr(custom_qa_versioning, name), name
        assert not hasattr(custom_qa_constants, name), name
        assert name not in custom_qa_constants.__all__


@pytest.mark.unit
def test_normalize_nfc_whitespace_and_reject_empty() -> None:
    # Combining accent → NFC
    raw = "cafe\u0301   room"
    assert normalize_question_text(raw, max_question_chars=500) == "café room"
    with pytest.raises(CustomQAQuestionsValidationError):
        normalize_question_text("   ", max_question_chars=500)
    with pytest.raises(CustomQAQuestionsValidationError):
        normalize_question_text(123, max_question_chars=500)  # type: ignore[arg-type]


@pytest.mark.unit
def test_question_id_fixed_32_hex() -> None:
    qid = question_id_for_text("What happened?")
    assert qid.startswith("q_")
    assert len(qid) == 2 + 32


@pytest.mark.unit
def test_canonicalize_legacy_string_explicit_scopes() -> None:
    qs, order = canonicalize_questions(
        ["Hello world"],
        max_questions=8,
        max_question_chars=500,
        max_total_question_chars=4000,
    )
    assert len(qs) == 1
    assert qs[0].scopes.global_scope is True
    assert qs[0].scopes.per_speaker is False
    assert order == (qs[0].question_id,)


@pytest.mark.unit
def test_canonicalize_rejects_mixed_list() -> None:
    with pytest.raises(CustomQAQuestionsValidationError, match="Mixed"):
        canonicalize_questions(
            ["a", {"text": "b", "scopes": {"global": True, "per_speaker": False}}],
            max_questions=8,
            max_question_chars=500,
            max_total_question_chars=4000,
        )


@pytest.mark.unit
def test_canonicalize_scope_union_and_hash_sorted() -> None:
    qs, order = canonicalize_questions(
        [
            {"text": "Zebra?", "scopes": {"global": True, "per_speaker": False}},
            {"text": "Apple?", "scopes": {"global": False, "per_speaker": True}},
            {"text": "Zebra?", "scopes": {"global": False, "per_speaker": True}},
        ],
        max_questions=8,
        max_question_chars=500,
        max_total_question_chars=4000,
    )
    assert len(qs) == 2
    assert order[0] == qs[0].question_id  # display: Zebra first
    zebra = next(q for q in qs if q.text == "Zebra?")
    assert zebra.scopes.global_scope and zebra.scopes.per_speaker
    h1 = questions_hash_for_canonical(qs)
    h2 = questions_hash_for_canonical(tuple(reversed(qs)))
    assert h1 == h2


@pytest.mark.unit
def test_outcome_truth_table() -> None:
    assert compute_structured_outcome(empty_questions=True, scheduled_statuses=[]) == (
        "empty_questions"
    )
    assert compute_structured_outcome(empty_questions=False, scheduled_statuses=[]) == (
        "no_scheduled_cells"
    )
    assert (
        compute_structured_outcome(
            empty_questions=False, scheduled_statuses=["answered", "answered"]
        )
        == "answered"
    )
    assert (
        compute_structured_outcome(
            empty_questions=False, scheduled_statuses=["abstained", "abstained"]
        )
        == "all_abstained"
    )
    assert (
        compute_structured_outcome(
            empty_questions=False, scheduled_statuses=["unavailable", "unavailable"]
        )
        == "all_unavailable"
    )
    assert (
        compute_structured_outcome(
            empty_questions=False, scheduled_statuses=["answered", "abstained"]
        )
        == "mixed"
    )
    assert (
        compute_structured_outcome(
            empty_questions=False,
            scheduled_statuses=["answered", "unavailable"],
        )
        == "partial"
    )


@pytest.mark.unit
def test_merge_evidence_pack_ids() -> None:
    assert merge_evidence_pack_ids(None, ["a"]) is None
    assert merge_evidence_pack_ids([], []) == []
    assert merge_evidence_pack_ids([], ["b", "a"]) == ["a", "b"]
    assert merge_evidence_pack_ids(["a"], ["b"]) == ["a", "b"]
