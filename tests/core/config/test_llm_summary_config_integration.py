"""Integration tests for analysis.llm_summary effort config."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from transcriptx.core.config import validate_config
from transcriptx.core.config.models.llm_summary import LLMSummarySettingsModel
from transcriptx.core.config.pydantic_bridge import (
    PYDANTIC_REGISTRY_PILOTS,
    capture_pilot_schema_golden,
)
from transcriptx.core.config.pydantic_registry import serialize_field_metadata
from transcriptx.core.config.registry import build_registry, get_default_config_dict
from transcriptx.core.utils.config.analysis import LLMSummaryConfig
from transcriptx.core.utils.config.main import TranscriptXConfig

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _llm_summary_spec():
    for spec in PYDANTIC_REGISTRY_PILOTS:
        if spec.pilot_id == "llm_summary_settings":
            return spec
    raise AssertionError("llm_summary_settings pilot not registered")


def test_default_effort_is_medium() -> None:
    assert TranscriptXConfig().analysis.llm_summary.effort == "medium"


def test_pydantic_defaults_match_dataclass_defaults() -> None:
    assert LLMSummarySettingsModel().model_dump() == asdict(LLMSummaryConfig())


def test_invalid_effort_rejected() -> None:
    errors = validate_config({"analysis": {"llm_summary": {"effort": "turbo"}}})
    assert "analysis.llm_summary.effort" in errors


@pytest.mark.parametrize("effort", ["low", "medium", "high", "max"])
def test_valid_efforts_accept(effort: str) -> None:
    errors = validate_config({"analysis": {"llm_summary": {"effort": effort}}})
    assert "analysis.llm_summary.effort" not in errors


def test_build_registry_llm_summary_matches_golden() -> None:
    golden = json.loads(
        (FIXTURES / "llm_summary_settings_registry_golden.json").read_text()
    )
    reg = build_registry()
    for key, expected in golden.items():
        assert key in reg, key
        assert serialize_field_metadata(reg[key]) == expected


def test_default_llm_summary_subtree_matches_golden() -> None:
    golden = json.loads(
        (FIXTURES / "llm_summary_settings_defaults_golden.json").read_text()
    )
    assert get_default_config_dict()["analysis"]["llm_summary"] == golden


def test_capture_pilot_schema_golden_matches_registry() -> None:
    spec = _llm_summary_spec()
    captured = capture_pilot_schema_golden(spec)
    reg = build_registry()
    for key, expected in captured.items():
        assert serialize_field_metadata(reg[key]) == expected
