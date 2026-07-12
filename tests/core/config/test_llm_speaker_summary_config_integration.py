"""Integration tests for analysis.llm_speaker_summary effort config."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from transcriptx.core.config import validate_config
from transcriptx.core.config.models.llm_speaker_summary import (
    LLMSpeakerSummarySettingsModel,
)
from transcriptx.core.config.pydantic_bridge import (
    PYDANTIC_REGISTRY_PILOTS,
    capture_pilot_schema_golden,
)
from transcriptx.core.config.pydantic_registry import serialize_field_metadata
from transcriptx.core.config.registry import build_registry, get_default_config_dict
from transcriptx.core.utils.config.analysis import LLMSpeakerSummaryConfig
from transcriptx.core.utils.config.file_overrides import load_config_file_into
from transcriptx.core.utils.config.main import TranscriptXConfig

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _llm_speaker_summary_spec():
    for spec in PYDANTIC_REGISTRY_PILOTS:
        if spec.pilot_id == "llm_speaker_summary_settings":
            return spec
    raise AssertionError("llm_speaker_summary_settings pilot not registered")


def test_default_effort_is_high() -> None:
    assert TranscriptXConfig().analysis.llm_speaker_summary.effort == "high"


def test_file_load_preserves_llm_speaker_summary_dataclass(tmp_path: Path) -> None:
    cfg = TranscriptXConfig()
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"analysis": {"llm_speaker_summary": {"effort": "medium"}}}),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(config_file))

    assert isinstance(cfg.analysis.llm_speaker_summary, LLMSpeakerSummaryConfig)
    assert cfg.analysis.llm_speaker_summary.effort == "medium"


def test_pydantic_defaults_match_dataclass_defaults() -> None:
    assert LLMSpeakerSummarySettingsModel().model_dump() == asdict(
        LLMSpeakerSummaryConfig()
    )


def test_invalid_effort_rejected() -> None:
    errors = validate_config({"analysis": {"llm_speaker_summary": {"effort": "turbo"}}})
    assert "analysis.llm_speaker_summary.effort" in errors


@pytest.mark.parametrize("effort", ["low", "medium", "high", "max"])
def test_valid_efforts_accept(effort: str) -> None:
    errors = validate_config({"analysis": {"llm_speaker_summary": {"effort": effort}}})
    assert "analysis.llm_speaker_summary.effort" not in errors


def test_build_registry_llm_speaker_summary_matches_golden() -> None:
    golden = json.loads(
        (FIXTURES / "llm_speaker_summary_settings_registry_golden.json").read_text()
    )
    reg = build_registry()
    for key, expected in golden.items():
        assert key in reg, key
        assert serialize_field_metadata(reg[key]) == expected


def test_default_llm_speaker_summary_subtree_matches_golden() -> None:
    golden = json.loads(
        (FIXTURES / "llm_speaker_summary_settings_defaults_golden.json").read_text()
    )
    assert get_default_config_dict()["analysis"]["llm_speaker_summary"] == golden


def test_capture_pilot_schema_golden_matches_registry() -> None:
    spec = _llm_speaker_summary_spec()
    captured = capture_pilot_schema_golden(spec)
    reg = build_registry()
    for key, expected in captured.items():
        assert serialize_field_metadata(reg[key]) == expected
