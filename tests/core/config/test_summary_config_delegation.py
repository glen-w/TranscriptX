"""Runtime delegation tests for analysis.summary."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path

import pytest

from transcriptx.core.config import validate_config
from transcriptx.core.config.models.summary import SummarySettingsModel
from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.analysis import AnalysisConfig, SummaryConfig
from transcriptx.core.utils.config.file_overrides import load_config_file_into

from .delegation_test_utils import (
    assert_is_dataclass_subtree,
    assert_ownership_invariant_unchanged,
    assert_subtree_shape_matches_pre_snapshot,
    assert_three_path_access,
)

_SCALAR_FIELDS = (
    "enabled",
    "require_highlights",
    "compute_highlights_if_missing",
    "allow_degraded",
)


def test_ownership_invariant_unchanged() -> None:
    assert_ownership_invariant_unchanged()


def test_default_shape_matches_pre_delegation_snapshot() -> None:
    assert_subtree_shape_matches_pre_snapshot("summary")


def test_asdict_parity_with_pydantic_model() -> None:
    assert asdict(SummaryConfig()) == SummarySettingsModel().model_dump()


@pytest.mark.parametrize("field", _SCALAR_FIELDS)
def test_three_path_default_access(field: str) -> None:
    expected = SummarySettingsModel().model_dump()[field]
    assert_three_path_access("summary", field, expected)


def test_nested_counts_attribute_access() -> None:
    cfg = AnalysisConfig()
    assert is_dataclass(type(cfg.summary.counts))
    assert cfg.summary.counts.theme_bullets == 6
    assert cfg.summary.sections.overview_enabled is True
    assert cfg.summary.commitments.max_per_owner == 3
    tx = TranscriptXConfig()
    assert tx.to_dict()["analysis"]["summary"]["counts"]["theme_bullets"] == 6


def test_file_override_nested_partial_merge(tmp_path: Path) -> None:
    cfg = TranscriptXConfig()
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"analysis": {"summary": {"counts": {"theme_bullets": 2}}}}),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(config_file))
    assert cfg.analysis.summary.counts.theme_bullets == 2
    assert cfg.analysis.summary.counts.tension_bullets == 5
    assert cfg.analysis.summary.enabled is True


def test_file_override_scalar_partial_merge(tmp_path: Path) -> None:
    cfg = TranscriptXConfig()
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"analysis": {"summary": {"enabled": False}}}),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(config_file))
    assert cfg.analysis.summary.enabled is False
    assert cfg.analysis.summary.compute_highlights_if_missing is True


def test_setattr_accepts_value_pydantic_would_reject_at_validation_boundary() -> None:
    cfg = AnalysisConfig()
    setattr(cfg.summary, "enabled", "maybe")
    assert cfg.summary.enabled == "maybe"
    errors = validate_config({"analysis": {"summary": {"enabled": "maybe"}}})
    assert "analysis.summary.enabled" in errors


def test_validate_config_invalid_payload_rejected() -> None:
    errors = validate_config({"analysis": {"summary": {"enabled": "maybe"}}})
    assert "analysis.summary.enabled" in errors


def test_is_dataclass_compatible_for_file_overrides() -> None:
    assert_is_dataclass_subtree("summary")
