from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.core.utils.config.env_overrides import apply_transcriptx_env
from transcriptx.core.utils.config.main import TranscriptXConfig
from transcriptx.core.utils.config.profile_loading import load_module_profiles
from transcriptx.core.utils.config.workflow import SpeakerGateConfig


@pytest.mark.unit
def test_transcriptx_config_load_order_file_profile_env(monkeypatch) -> None:
    calls: list[str] = []

    def _file_loader(config_obj, _config_file):
        calls.append("file")
        config_obj.output.dynamic_charts = "off"

    def _profile_loader(config_obj):
        calls.append("profile")
        config_obj.output.dynamic_charts = "on"

    def _env_loader(config_obj):
        calls.append("env")
        config_obj.output.dynamic_charts = "auto"

    monkeypatch.setattr(
        "transcriptx.core.utils.config.file_overrides.load_config_file_into",
        _file_loader,
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.config.profile_loading.load_module_profiles",
        _profile_loader,
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.config.env_overrides.apply_transcriptx_env", _env_loader
    )

    cfg = TranscriptXConfig(config_file="dummy.json")
    assert calls == ["file", "profile", "env"]
    assert cfg.output.dynamic_charts == "auto"


@pytest.mark.unit
def test_apply_transcriptx_env_speaker_gate_coercion_and_validation(
    monkeypatch,
) -> None:
    cfg = TranscriptXConfig()
    cfg.workflow.speaker_gate = SpeakerGateConfig()

    monkeypatch.setenv("TRANSCRIPTX_SPEAKER_GATE_THRESHOLD_VALUE", "-5")
    monkeypatch.setenv("TRANSCRIPTX_SPEAKER_GATE_THRESHOLD_TYPE", "invalid-type")
    monkeypatch.setenv("TRANSCRIPTX_SPEAKER_GATE_MODE", "invalid-mode")
    monkeypatch.setenv("TRANSCRIPTX_SPEAKER_GATE_EXEMPLAR_COUNT", "-3")

    apply_transcriptx_env(cfg)

    gate = cfg.workflow.speaker_gate
    assert gate.threshold_type == "absolute"
    assert gate.mode == "warn"
    assert gate.threshold_value == 0.0
    assert gate.exemplar_count == 0


@pytest.mark.unit
def test_load_module_profiles_env_acts_model_overrides_profile(monkeypatch) -> None:
    class _ProfileManager:
        def load_profile(self, module: str, _profile_name: str):
            if module == "acts":
                return {"config": {"ml_model_name": "profile-model"}}
            return None

    config = SimpleNamespace(
        analysis=SimpleNamespace(
            active_topic_modeling_profile="default",
            active_acts_profile="default",
            active_tag_extraction_profile="default",
            active_qa_analysis_profile="default",
            active_temporal_dynamics_profile="default",
            active_vectorization_profile="default",
            topic_modeling=SimpleNamespace(),
            acts=SimpleNamespace(ml_model_name="baseline-model"),
            tag_extraction=SimpleNamespace(),
            qa_analysis=SimpleNamespace(),
            temporal_dynamics=SimpleNamespace(),
            vectorization=SimpleNamespace(),
        ),
        active_workflow_profile="default",
        workflow=SimpleNamespace(),
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.profile_manager.get_profile_manager",
        lambda: _ProfileManager(),
    )
    monkeypatch.setenv("TRANSCRIPTX_ACTS_MODEL", "env-model")

    load_module_profiles(config)
    assert config.analysis.acts.ml_model_name == "env-model"
