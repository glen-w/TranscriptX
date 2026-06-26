"""Registry parity tests for Pydantic-backed analysis.acts settings."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from transcriptx.core.analysis.acts.config import ActClassificationConfig
from transcriptx.core.config.models.acts import ActsSettingsModel
from transcriptx.core.config.pydantic_bridge import (
    PYDANTIC_REGISTRY_PILOTS,
    all_pydantic_field_dotpaths,
    capture_pilot_schema_golden,
)
from transcriptx.core.config.pydantic_registry import serialize_field_metadata
from transcriptx.core.config.registry import build_registry, get_default_config_dict
from transcriptx.core.utils.config.analysis import ActsConfig

FIXTURES = Path(__file__).resolve().parent / "fixtures"

_ACT_CLASSIFICATION_ONLY_FIELDS = frozenset(
    name
    for name in ActClassificationConfig.__dataclass_fields__
    if name not in ActsConfig.__dataclass_fields__
)


def _acts_spec():
    for spec in PYDANTIC_REGISTRY_PILOTS:
        if spec.pilot_id == "acts":
            return spec
    raise AssertionError("acts pilot not registered")


def test_build_registry_acts_matches_golden() -> None:
    golden = json.loads((FIXTURES / "acts_registry_golden.json").read_text())
    reg = build_registry()
    for key, expected in golden.items():
        assert key in reg, key
        assert serialize_field_metadata(reg[key]) == expected


def test_pydantic_defaults_match_dataclass_defaults() -> None:
    assert ActsSettingsModel().model_dump() == asdict(ActsConfig())


def test_default_acts_subtree_matches_golden() -> None:
    golden = json.loads((FIXTURES / "acts_defaults_golden.json").read_text())
    assert get_default_config_dict()["analysis"]["acts"] == golden


def test_acts_model_json_schema_snapshot() -> None:
    golden = json.loads((FIXTURES / "acts_model_schema_golden.json").read_text())
    assert ActsSettingsModel.model_json_schema() == golden


def test_registry_excludes_act_classification_config_only_fields() -> None:
    pilot_keys = all_pydantic_field_dotpaths()
    acts_keys = {key for key in pilot_keys if key.startswith("analysis.acts.")}
    for field_name in _ACT_CLASSIFICATION_ONLY_FIELDS:
        assert f"analysis.acts.{field_name}" not in acts_keys, field_name
    assert "analysis.acts.include_probabilities" not in pilot_keys
    assert "analysis.acts.both_methods_output_dir" not in pilot_keys


def test_capture_pilot_schema_golden_matches_registry() -> None:
    spec = _acts_spec()
    captured = capture_pilot_schema_golden(spec)
    reg = build_registry()
    for key, expected in captured.items():
        assert serialize_field_metadata(reg[key]) == expected
