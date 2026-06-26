"""Registry parity tests for Pydantic-backed llm.* settings."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from transcriptx.core.config.models.llm import LLMSettingsModel
from transcriptx.core.config.pydantic_bridge import (
    PYDANTIC_REGISTRY_PILOTS,
    capture_pilot_schema_golden,
)
from transcriptx.core.config.pydantic_registry import serialize_field_metadata
from transcriptx.core.config.registry import build_registry, get_default_config_dict
from transcriptx.core.utils.config.system import LLMConfig

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _llm_spec():
    for spec in PYDANTIC_REGISTRY_PILOTS:
        if spec.pilot_id == "llm":
            return spec
    raise AssertionError("llm pilot not registered")


def test_build_registry_llm_matches_golden() -> None:
    golden = json.loads((FIXTURES / "llm_registry_golden.json").read_text())
    reg = build_registry()
    for key, expected in golden.items():
        assert key in reg, key
        assert serialize_field_metadata(reg[key]) == expected


def test_pydantic_defaults_match_dataclass_defaults() -> None:
    # LLMConfig uses the same field names and defaults as LLMSettingsModel.
    assert LLMSettingsModel().model_dump() == asdict(LLMConfig())


def test_default_llm_subtree_matches_golden() -> None:
    golden = json.loads((FIXTURES / "llm_defaults_golden.json").read_text())
    assert get_default_config_dict()["llm"] == golden


def test_llm_model_json_schema_snapshot() -> None:
    golden = json.loads((FIXTURES / "llm_model_schema_golden.json").read_text())
    assert LLMSettingsModel.model_json_schema() == golden


def test_api_key_registry_metadata_hidden_and_advanced() -> None:
    reg = build_registry()
    meta = reg["llm.api_key"]
    assert meta.sensitivity == "hidden"
    assert meta.advanced is True
    serialized = serialize_field_metadata(meta)
    assert "sk-" not in json.dumps(serialized)
    assert serialized["default"] is None


def test_capture_pilot_schema_golden_matches_registry() -> None:
    spec = _llm_spec()
    captured = capture_pilot_schema_golden(spec)
    reg = build_registry()
    for key, expected in captured.items():
        assert serialize_field_metadata(reg[key]) == expected
