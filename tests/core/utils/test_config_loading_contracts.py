"""Tests for config loading contracts."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from transcriptx.core.utils.config.env_overrides import apply_transcriptx_env
from transcriptx.core.utils.config.config_errors import ConfigLoadError
from transcriptx.core.utils.config.file_overrides import load_config_file_into
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


@pytest.mark.unit
def test_load_module_profiles_uses_runtime_adapters(monkeypatch) -> None:
    class _FakeAdapter:
        target_id = "acts"

        def get_active_profile_name(self, config_obj):
            return config_obj.analysis.active_acts_profile

        def get_target_config_obj(self, config_obj):
            return config_obj.analysis.acts

    class _ProfileManager:
        def load_profile(self, module: str, _profile_name: str):
            if module == "acts":
                return {"config": {"ml_model_name": "adapter-model"}}
            return None

    config = SimpleNamespace(
        analysis=SimpleNamespace(
            active_acts_profile="default",
            acts=SimpleNamespace(ml_model_name="baseline-model"),
        ),
        workflow=SimpleNamespace(),
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.config.profile_loading.iter_runtime_profile_target_adapters",
        lambda: (_FakeAdapter(),),
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.profile_manager.get_profile_manager",
        lambda: _ProfileManager(),
    )
    monkeypatch.delenv("TRANSCRIPTX_ACTS_MODEL", raising=False)

    load_module_profiles(config)
    assert config.analysis.acts.ml_model_name == "adapter-model"


@pytest.mark.unit
def test_load_config_file_uses_adapter_payload_contract(monkeypatch, tmp_path) -> None:
    class _FakeAdapter:
        target_id = "custom_target"
        activation_key = "analysis.active_custom_profile"
        config_path = ("analysis", "custom_target")

        def get_activation_from_payload(self, payload):
            analysis = payload.get("analysis", {})
            if "active_custom_profile" not in analysis:
                return (False, "default")
            return (True, str(analysis["active_custom_profile"]))

        def get_target_payload(self, payload):
            analysis = payload.get("analysis", {})
            value = analysis.get("custom_target")
            if not isinstance(value, dict):
                return (False, {})
            return (True, value)

        def set_active_profile_name(self, config_obj, profile_name):
            config_obj.analysis.active_custom_profile = profile_name

        def get_target_config_obj(self, config_obj):
            return config_obj.analysis.custom_target

    monkeypatch.setattr(
        "transcriptx.core.utils.config.file_overrides.iter_all_profile_target_adapters",
        lambda: (_FakeAdapter(),),
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.config.file_overrides.validate_raw_config_dict",
        lambda _payload: None,
    )
    config_file = tmp_path / "cfg.json"
    config_file.write_text(
        '{"analysis":{"active_custom_profile":"team","custom_target":{"param":42}}}',
        encoding="utf-8",
    )
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(
            active_custom_profile="default",
            custom_target=SimpleNamespace(param=0),
        ),
        input=SimpleNamespace(),
        output=SimpleNamespace(),
        logging=SimpleNamespace(),
        audio_preprocessing=SimpleNamespace(),
        workflow=SimpleNamespace(),
        group_analysis=SimpleNamespace(),
        dashboard=SimpleNamespace(),
    )

    load_config_file_into(cfg, str(config_file))
    assert cfg.analysis.active_custom_profile == "team"
    assert cfg.analysis.custom_target.param == 42


@pytest.mark.unit
def test_file_overrides_apply_order_base_then_adapter_then_bucket(
    monkeypatch, tmp_path
) -> None:
    calls: list[str] = []

    class _FakeAdapter:
        target_id = "custom_target"
        activation_key = "analysis.active_custom_profile"
        config_path = ("analysis", "custom_target")

        def get_activation_from_payload(self, payload):
            analysis = payload.get("analysis", {})
            if "active_custom_profile" not in analysis:
                return (False, "default")
            return (True, str(analysis["active_custom_profile"]))

        def get_target_payload(self, payload):
            analysis = payload.get("analysis", {})
            value = analysis.get("custom_target")
            if not isinstance(value, dict):
                return (False, {})
            return (True, value)

        def set_active_profile_name(self, config_obj, profile_name):
            calls.append("adapter_activation")
            config_obj.analysis.active_custom_profile = profile_name

        def get_target_config_obj(self, config_obj):
            return config_obj.analysis.custom_target

    def _spy_apply_profile_to_config(config_obj, payload):
        # Apply runs on a deep candidate (Config 1.7); detect by payload shape, not live id.
        if "timeout_quick_seconds" in payload:
            calls.append("base_workflow")
        elif "param" in payload:
            calls.append("adapter_target")
        for key, value in payload.items():
            setattr(config_obj, key, value)

    monkeypatch.setattr(
        "transcriptx.core.utils.config.file_overrides.iter_all_profile_target_adapters",
        lambda: (_FakeAdapter(),),
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.config.file_overrides.validate_raw_config_dict",
        lambda _payload: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.config.file_overrides.apply_profile_to_config",
        _spy_apply_profile_to_config,
    )
    config_file = tmp_path / "cfg_order.json"
    config_file.write_text(
        (
            '{"analysis":{"quality_filtering_profiles":{"balanced":{"thresholds":{"x":[1,2]}}},'
            '"active_custom_profile":"team","custom_target":{"param":42}},'
            '"workflow":{"timeout_quick_seconds":11}}'
        ),
        encoding="utf-8",
    )
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(
            active_custom_profile="default",
            custom_target=SimpleNamespace(param=0),
            quality_filtering_profiles={},
        ),
        input=SimpleNamespace(),
        output=SimpleNamespace(),
        logging=SimpleNamespace(),
        audio_preprocessing=SimpleNamespace(),
        workflow=SimpleNamespace(timeout_quick_seconds=0),
        group_analysis=SimpleNamespace(),
        dashboard=SimpleNamespace(),
    )

    load_config_file_into(cfg, str(config_file))
    assert calls.index("base_workflow") < calls.index("adapter_target")
    assert cfg.analysis.quality_filtering_profiles["balanced"]["thresholds"]["x"] == (
        1,
        2,
    )


@pytest.mark.unit
def test_load_config_file_root_bool_flags_are_coerced(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "transcriptx.core.utils.config.file_overrides.iter_all_profile_target_adapters",
        lambda: (),
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.config.file_overrides.validate_raw_config_dict",
        lambda _payload: None,
    )
    config_file = tmp_path / "cfg_flags.json"
    config_file.write_text(
        json.dumps({"use_emojis": 1, "core_mode": ""}),
        encoding="utf-8",
    )
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(),
        input=SimpleNamespace(),
        output=SimpleNamespace(),
        logging=SimpleNamespace(),
        audio_preprocessing=SimpleNamespace(),
        workflow=SimpleNamespace(),
        group_analysis=SimpleNamespace(),
        dashboard=SimpleNamespace(),
        use_emojis=False,
        core_mode=True,
    )

    load_config_file_into(cfg, str(config_file))
    assert cfg.use_emojis is True
    assert cfg.core_mode is False


@pytest.mark.unit
def test_load_config_file_preserves_config_load_error(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "transcriptx.core.utils.config.file_overrides.unwrap_config_payload",
        lambda _raw: (_ for _ in ()).throw(
            ConfigLoadError("invalid contract", code="invalid_value")
        ),
    )
    config_file = tmp_path / "cfg_invalid.json"
    config_file.write_text("{}", encoding="utf-8")
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(),
        input=SimpleNamespace(),
        output=SimpleNamespace(),
        logging=SimpleNamespace(),
        audio_preprocessing=SimpleNamespace(),
        workflow=SimpleNamespace(),
        group_analysis=SimpleNamespace(),
        dashboard=SimpleNamespace(),
    )

    with pytest.raises(ConfigLoadError, match="invalid contract"):
        load_config_file_into(cfg, str(config_file))
