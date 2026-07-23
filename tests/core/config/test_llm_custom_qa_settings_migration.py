"""Config migration idempotence for llm_custom_qa settings."""

from __future__ import annotations

import pytest

from transcriptx.core.config.models.llm_custom_qa import LLMCustomQASettingsModel


@pytest.mark.unit
def test_legacy_string_library_migrates_explicit_scopes() -> None:
    m = LLMCustomQASettingsModel.model_validate(
        {"saved_questions": ["What next?", "Who spoke?"]}
    )
    assert len(m.saved_questions) == 2
    assert m.saved_questions[0].scopes.global_scope is True
    assert m.saved_questions[0].scopes.per_speaker is False
    # load-save-load stability
    dumped = m.model_dump(by_alias=True)
    m2 = LLMCustomQASettingsModel.model_validate(dumped)
    assert m2.model_dump(by_alias=True) == dumped


@pytest.mark.unit
def test_reject_mixed_saved_questions() -> None:
    with pytest.raises(Exception):
        LLMCustomQASettingsModel.model_validate(
            {
                "saved_questions": [
                    "a",
                    {"text": "b", "scopes": {"global": True, "per_speaker": False}},
                ]
            }
        )


@pytest.mark.unit
def test_evidence_pack_ids_null_default() -> None:
    m = LLMCustomQASettingsModel()
    assert m.evidence_pack_ids is None
    m2 = LLMCustomQASettingsModel.model_validate({"evidence_pack_ids": []})
    assert m2.evidence_pack_ids == []


@pytest.mark.unit
def test_saved_question_scopes_and_extra_forbid() -> None:
    from pydantic import ValidationError

    m = LLMCustomQASettingsModel.model_validate(
        {
            "saved_questions": [
                {
                    "text": "Who decided?",
                    "scopes": {"global": False, "per_speaker": True},
                }
            ]
        }
    )
    assert m.saved_questions[0].scopes.global_scope is False
    assert m.saved_questions[0].scopes.per_speaker is True
    with pytest.raises(ValidationError):
        LLMCustomQASettingsModel.model_validate(
            {"saved_questions": [{"text": "x", "scopes": {"global": True}, "extra": 1}]}
        )
