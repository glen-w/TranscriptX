"""Runtime delegation tests for analysis.llm_speaker_summary."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from transcriptx.core.config import validate_config
from transcriptx.core.config.models.llm_speaker_summary import (
    LLMSpeakerSummarySettingsModel,
)
from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.analysis import (
    AnalysisConfig,
    LLMSpeakerSummaryConfig,
)
from transcriptx.core.utils.config.file_overrides import load_config_file_into

from .delegation_test_utils import (
    assert_is_dataclass_subtree,
    assert_ownership_invariant_unchanged,
    assert_subtree_shape_matches_pre_snapshot,
    assert_three_path_access,
)

_FIELDS = tuple(LLMSpeakerSummarySettingsModel.model_fields.keys())


def test_ownership_invariant_unchanged() -> None:
    assert_ownership_invariant_unchanged()


def test_default_shape_matches_pre_delegation_snapshot() -> None:
    assert_subtree_shape_matches_pre_snapshot("llm_speaker_summary")


def test_asdict_parity_with_pydantic_model() -> None:
    assert (
        asdict(LLMSpeakerSummaryConfig())
        == LLMSpeakerSummarySettingsModel().model_dump()
    )


@pytest.mark.parametrize("field", _FIELDS)
def test_three_path_default_access(field: str) -> None:
    expected = LLMSpeakerSummarySettingsModel().model_dump()[field]
    assert_three_path_access("llm_speaker_summary", field, expected)


def test_file_override_partial_merge(tmp_path: Path) -> None:
    cfg = TranscriptXConfig()
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"analysis": {"llm_speaker_summary": {"effort": "medium"}}}),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(config_file))
    assert cfg.analysis.llm_speaker_summary.effort == "medium"


def test_setattr_accepts_value_pydantic_would_reject_at_validation_boundary() -> None:
    cfg = AnalysisConfig()
    setattr(cfg.llm_speaker_summary, "effort", "extreme")
    assert cfg.llm_speaker_summary.effort == "extreme"
    errors = validate_config(
        {"analysis": {"llm_speaker_summary": {"effort": "extreme"}}}
    )
    assert "analysis.llm_speaker_summary.effort" in errors


def test_validate_config_invalid_payload_rejected() -> None:
    errors = validate_config(
        {"analysis": {"llm_speaker_summary": {"effort": "extreme"}}}
    )
    assert "analysis.llm_speaker_summary.effort" in errors


def test_is_dataclass_compatible_for_file_overrides() -> None:
    assert_is_dataclass_subtree("llm_speaker_summary")
