"""Runtime delegation tests for analysis.voice (Batch 5)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from transcriptx.core.config import validate_config
from transcriptx.core.config.models.voice import VoiceSettingsModel
from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.analysis import AnalysisConfig, VoiceConfig
from transcriptx.core.utils.config.file_overrides import load_config_file_into

from .delegation_test_utils import (
    assert_is_dataclass_subtree,
    assert_ownership_invariant_unchanged,
    assert_subtree_shape_matches_pre_snapshot,
    assert_three_path_access,
)

_FIELDS = tuple(VoiceSettingsModel.model_fields.keys())


def test_ownership_invariant_unchanged() -> None:
    assert_ownership_invariant_unchanged()


def test_default_shape_matches_pre_delegation_snapshot() -> None:
    assert_subtree_shape_matches_pre_snapshot("voice")


def test_asdict_parity_with_pydantic_model() -> None:
    assert asdict(VoiceConfig()) == VoiceSettingsModel().model_dump()


@pytest.mark.parametrize("field", _FIELDS)
def test_three_path_default_access(field: str) -> None:
    expected = VoiceSettingsModel().model_dump()[field]
    assert_three_path_access("voice", field, expected)


def test_setattr_updates_readable_value() -> None:
    cfg = AnalysisConfig()
    setattr(cfg.voice, "enabled", False)
    assert cfg.voice.enabled is False
    assert TranscriptXConfig().analysis.voice.enabled is True


def test_setattr_accepts_value_pydantic_would_reject_at_validation_boundary() -> None:
    cfg = AnalysisConfig()
    setattr(cfg.voice, "sample_rate", "fast")
    assert cfg.voice.sample_rate == "fast"
    errors = validate_config({"analysis": {"voice": {"sample_rate": "fast"}}})
    assert "analysis.voice.sample_rate" in errors


def test_file_override_partial_merge(tmp_path: Path) -> None:
    cfg = TranscriptXConfig()
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"analysis": {"voice": {"deep_mode": True}}}),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(config_file))
    assert cfg.analysis.voice.deep_mode is True
    assert cfg.analysis.voice.enabled is True


def test_validate_config_invalid_payload_rejected() -> None:
    errors = validate_config({"analysis": {"voice": {"vad_mode": "loud"}}})
    assert "analysis.voice.vad_mode" in errors


def test_is_dataclass_compatible_for_file_overrides() -> None:
    assert_is_dataclass_subtree("voice")
