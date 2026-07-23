"""Unit tests for LLM summary effort tier settings (0.3.2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from transcriptx.core.config.models.llm_action_items import LLMActionItemsSettingsModel
from transcriptx.core.config.models.llm_speaker_summary import (
    LLMSpeakerSummarySettingsModel,
)
from transcriptx.core.config.models.llm_summary import LLMSummarySettingsModel


@pytest.mark.unit
@pytest.mark.parametrize(
    "model_cls",
    [
        LLMSummarySettingsModel,
        LLMSpeakerSummarySettingsModel,
        LLMActionItemsSettingsModel,
    ],
)
def test_llm_effort_tiers_accept_canonical_values(model_cls) -> None:
    for effort in ("low", "medium", "high", "max"):
        model = model_cls(effort=effort)
        assert model.effort == effort


@pytest.mark.unit
def test_llm_effort_rejects_unknown_tier() -> None:
    with pytest.raises(ValidationError):
        LLMSummarySettingsModel(effort="ultra")
    with pytest.raises(ValidationError):
        LLMSpeakerSummarySettingsModel(effort="turbo")
    with pytest.raises(ValidationError):
        LLMActionItemsSettingsModel(effort="")


@pytest.mark.unit
def test_llm_summary_effort_default_is_high() -> None:
    assert LLMSummarySettingsModel().effort == "high"
    assert LLMSpeakerSummarySettingsModel().effort == "high"
    assert LLMActionItemsSettingsModel().effort == "max"
