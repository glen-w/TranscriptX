"""Unit tests for profile_loading.apply_profile_to_config / load_module_profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.profile_loading import (
    apply_profile_to_config,
    load_module_profiles,
)
from transcriptx.core.utils.config.workflow import SpeakerGateConfig

from .delegation_test_utils import without_transcriptx_env


@dataclass
class _NoValidateTarget:
    alpha: int = 1
    ngram_range: tuple[int, int] = (1, 2)
    labels: list[str] = field(default_factory=lambda: ["a"])


def test_apply_profile_known_keys_and_ignores_unknown() -> None:
    target = _NoValidateTarget()
    apply_profile_to_config(
        target, {"alpha": 9, "unknown_key": 123, "labels": ["x", "y", "z"]}
    )
    assert target.alpha == 9
    assert target.labels == ["x", "y", "z"]
    assert not hasattr(target, "unknown_key")


def test_apply_profile_numeric_len2_list_becomes_tuple() -> None:
    target = _NoValidateTarget()
    apply_profile_to_config(target, {"ngram_range": [2, 4]})
    assert target.ngram_range == (2, 4)
    assert isinstance(target.ngram_range, tuple)


def test_apply_profile_non_numeric_len2_list_unchanged() -> None:
    target = _NoValidateTarget()
    apply_profile_to_config(target, {"labels": ["hi", "there"]})
    assert target.labels == ["hi", "there"]
    assert isinstance(target.labels, list)


def test_apply_profile_calls_validate_on_speaker_gate() -> None:
    gate = SpeakerGateConfig()
    apply_profile_to_config(
        gate,
        {
            "threshold_type": "PERCENTAGE",  # normalize via validate()
            "threshold_value": 150.0,  # clamp to 100 for percentage
            "mode": "WARN",
        },
    )
    assert gate.threshold_type == "percentage"
    assert gate.threshold_value == 100.0
    assert gate.mode == "warn"


def test_apply_profile_without_validate_is_fine() -> None:
    target = _NoValidateTarget()
    apply_profile_to_config(target, {"alpha": 3})
    assert target.alpha == 3


def test_load_module_profiles_missing_or_empty_leaves_defaults(monkeypatch) -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
    before = cfg.analysis.acts.method

    class _PM:
        def load_profile(self, target_id: str, name: str) -> Any:
            if target_id == "acts":
                return None
            return {}

    monkeypatch.setattr(
        "transcriptx.core.utils.profile_manager.get_profile_manager",
        lambda: _PM(),
    )
    load_module_profiles(cfg)
    assert cfg.analysis.acts.method == before


def test_load_module_profiles_no_config_key_leaves_defaults(monkeypatch) -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
    before = cfg.analysis.acts.ml_model_name

    class _PM:
        def load_profile(self, target_id: str, name: str) -> dict[str, Any]:
            return {"meta": "no-config-key"}

    monkeypatch.setattr(
        "transcriptx.core.utils.profile_manager.get_profile_manager",
        lambda: _PM(),
    )
    load_module_profiles(cfg)
    assert cfg.analysis.acts.ml_model_name == before


def test_load_module_profiles_applies_config_payload(monkeypatch) -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()

    class _PM:
        def load_profile(self, target_id: str, name: str) -> dict[str, Any] | None:
            if target_id == "acts":
                return {"config": {"method": "rules", "ml_model_name": "tiny-model"}}
            return None

    monkeypatch.setattr(
        "transcriptx.core.utils.profile_manager.get_profile_manager",
        lambda: _PM(),
    )
    load_module_profiles(cfg)
    assert cfg.analysis.acts.method == "rules"
    assert cfg.analysis.acts.ml_model_name == "tiny-model"
