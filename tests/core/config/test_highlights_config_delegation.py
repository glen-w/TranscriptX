"""Runtime delegation tests for analysis.highlights."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path

import pytest

from transcriptx.core.config import validate_config
from transcriptx.core.config.models.highlights import HighlightsSettingsModel
from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.analysis import AnalysisConfig, HighlightsConfig
from transcriptx.core.utils.config.file_overrides import load_config_file_into

from .delegation_test_utils import (
    assert_is_dataclass_subtree,
    assert_ownership_invariant_unchanged,
    assert_subtree_shape_matches_pre_snapshot,
    assert_three_path_access,
)

_SCALAR_FIELDS = ("enabled",)


def test_ownership_invariant_unchanged() -> None:
    assert_ownership_invariant_unchanged()


def test_default_shape_matches_pre_delegation_snapshot() -> None:
    assert_subtree_shape_matches_pre_snapshot("highlights")


def test_asdict_parity_with_pydantic_model() -> None:
    assert asdict(HighlightsConfig()) == HighlightsSettingsModel().model_dump()


@pytest.mark.parametrize("field", _SCALAR_FIELDS)
def test_three_path_default_access(field: str) -> None:
    expected = HighlightsSettingsModel().model_dump()[field]
    assert_three_path_access("highlights", field, expected)


def test_nested_attribute_access() -> None:
    cfg = AnalysisConfig()
    assert is_dataclass(type(cfg.highlights.counts))
    assert cfg.highlights.counts.total_highlights == 15
    assert cfg.highlights.weights.intensity == 0.4
    assert cfg.highlights.cold_open.window_policy == "seconds"
    tx = TranscriptXConfig()
    assert tx.to_dict()["analysis"]["highlights"]["thresholds"]["min_quote_words"] == 4


def test_file_override_nested_partial_merge(tmp_path: Path) -> None:
    cfg = TranscriptXConfig()
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "analysis": {
                    "highlights": {
                        "weights": {"intensity": 0.55},
                        "cold_open": {"window_seconds": 45.0},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(config_file))
    assert cfg.analysis.highlights.weights.intensity == 0.55
    assert cfg.analysis.highlights.weights.conflict == 0.3
    assert cfg.analysis.highlights.cold_open.window_seconds == 45.0
    assert cfg.analysis.highlights.enabled is True


def test_setattr_accepts_value_pydantic_would_reject_at_validation_boundary() -> None:
    cfg = AnalysisConfig()
    setattr(cfg.highlights, "enabled", "maybe")
    assert cfg.highlights.enabled == "maybe"
    errors = validate_config({"analysis": {"highlights": {"enabled": "maybe"}}})
    assert "analysis.highlights.enabled" in errors


def test_validate_config_invalid_payload_rejected() -> None:
    errors = validate_config({"analysis": {"highlights": {"enabled": "maybe"}}})
    assert "analysis.highlights.enabled" in errors


def test_is_dataclass_compatible_for_file_overrides() -> None:
    assert_is_dataclass_subtree("highlights")
