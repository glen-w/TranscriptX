"""Runtime delegation tests for analysis.pauses (Batch 5)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from transcriptx.core.config import validate_config
from transcriptx.core.config.models.pauses import PausesSettingsModel
from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.analysis import AnalysisConfig, PausesConfig
from transcriptx.core.utils.config.file_overrides import load_config_file_into

from .delegation_test_utils import (
    assert_is_dataclass_subtree,
    assert_ownership_invariant_unchanged,
    assert_subtree_shape_matches_pre_snapshot,
    assert_three_path_access,
)

_FIELDS = tuple(PausesSettingsModel.model_fields.keys())


def test_ownership_invariant_unchanged() -> None:
    assert_ownership_invariant_unchanged()


def test_default_shape_matches_pre_delegation_snapshot() -> None:
    assert_subtree_shape_matches_pre_snapshot("pauses")


def test_asdict_parity_with_pydantic_model() -> None:
    assert asdict(PausesConfig()) == PausesSettingsModel().model_dump()


@pytest.mark.parametrize("field", _FIELDS)
def test_three_path_default_access(field: str) -> None:
    expected = PausesSettingsModel().model_dump()[field]
    assert_three_path_access("pauses", field, expected)


def test_setattr_updates_without_pydantic_revalidation() -> None:
    cfg = AnalysisConfig()
    setattr(cfg.pauses, "min_long_pause_seconds", 99.0)
    assert cfg.pauses.min_long_pause_seconds == 99.0
    errors = validate_config({"analysis": {"pauses": {"min_long_pause_seconds": 99.0}}})
    assert "analysis.pauses.min_long_pause_seconds" not in errors


def test_setattr_accepts_value_pydantic_would_reject_at_validation_boundary() -> None:
    cfg = AnalysisConfig()
    setattr(cfg.pauses, "min_long_pause_seconds", "not-a-float")
    assert cfg.pauses.min_long_pause_seconds == "not-a-float"
    errors = validate_config(
        {"analysis": {"pauses": {"min_long_pause_seconds": "not-a-float"}}}
    )
    assert "analysis.pauses.min_long_pause_seconds" in errors


def test_file_override_partial_merge(tmp_path: Path) -> None:
    cfg = TranscriptXConfig()
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"analysis": {"pauses": {"min_long_pause_seconds": 3.0}}}),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(config_file))
    assert cfg.analysis.pauses.min_long_pause_seconds == 3.0
    assert cfg.analysis.pauses.post_question_multiplier == 1.5


def test_validate_config_invalid_payload_rejected() -> None:
    errors = validate_config(
        {"analysis": {"pauses": {"min_long_pause_seconds": "long"}}}
    )
    assert "analysis.pauses.min_long_pause_seconds" in errors


def test_is_dataclass_compatible_for_file_overrides() -> None:
    assert_is_dataclass_subtree("pauses")
