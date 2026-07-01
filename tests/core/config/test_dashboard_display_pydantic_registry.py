"""Registry parity tests for Pydantic-backed dashboard display settings."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.config.models.dashboard_display import (
    DashboardDisplaySettingsModel,
)
from transcriptx.core.config.pydantic_registry import serialize_field_metadata
from transcriptx.core.config.registry import build_registry, get_default_config_dict

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_build_registry_dashboard_display_matches_golden() -> None:
    golden = json.loads(
        (FIXTURES / "dashboard_display_registry_golden.json").read_text()
    )
    reg = build_registry()
    for key, expected in golden.items():
        assert key in reg, key
        assert serialize_field_metadata(reg[key]) == expected


def test_pydantic_defaults_match_dashboard_config_defaults() -> None:
    pydantic_defaults = DashboardDisplaySettingsModel().model_dump()
    dash = get_default_config_dict()["dashboard"]
    for key, value in pydantic_defaults.items():
        assert dash[key] == value


def test_dashboard_display_defaults_match_golden() -> None:
    golden = json.loads(
        (FIXTURES / "dashboard_display_defaults_golden.json").read_text()
    )
    dash = get_default_config_dict()["dashboard"]
    assert {k: dash[k] for k in golden} == golden


def test_dashboard_overview_fields_use_pydantic_metadata() -> None:
    reg = build_registry()
    assert reg["dashboard.overview_max_items"].min == 1
    assert "skip" in reg["dashboard.overview_missing_behavior"].choices
    assert reg["dashboard.overview_charts"].description
