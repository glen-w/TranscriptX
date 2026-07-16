"""System / workflow / Dashboard runtime delegation parity (Step 1.6)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, fields
from pathlib import Path

import pytest

from transcriptx.core.config.models.audio_preprocessing import (
    AudioPreprocessingSettingsModel,
)
from transcriptx.core.config.models.dashboard_display import (
    DashboardDisplaySettingsModel,
)
from transcriptx.core.config.models.dashboard_overview import (
    DashboardOverviewSettingsModel,
)
from transcriptx.core.config.models.group_analysis import GroupAnalysisSettingsModel
from transcriptx.core.config.models.input import InputSettingsModel
from transcriptx.core.config.models.llm import LLMSettingsModel
from transcriptx.core.config.models.logging import LoggingSettingsModel
from transcriptx.core.config.models.metadata import MetadataSettingsModel
from transcriptx.core.config.models.output import OutputSettingsModel
from transcriptx.core.config.models.workflow import (
    SpeakerGateSettingsModel,
    WorkflowSettingsModel,
)
from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.env_overrides import apply_transcriptx_env
from transcriptx.core.utils.config.file_overrides import load_config_file_into
from transcriptx.core.utils.config.system import (
    AudioPreprocessingConfig,
    LLMConfig,
    LoggingConfig,
)
from transcriptx.core.utils.config.workflow import (
    DashboardConfig,
    GroupAnalysisConfig,
    InputConfig,
    MetadataConfig,
    OutputConfig,
    SpeakerGateConfig,
    WorkflowConfig,
)

from .delegation_test_utils import (
    assert_mutable_container_independence,
    assert_normalized_defaults_parity,
    assert_ownership_invariant_unchanged,
    without_transcriptx_env,
)

_ROOT_CASES = (
    ("llm", LLMConfig, LLMSettingsModel, "llm"),
    ("logging", LoggingConfig, LoggingSettingsModel, "logging"),
    (
        "audio_preprocessing",
        AudioPreprocessingConfig,
        AudioPreprocessingSettingsModel,
        "audio_preprocessing",
    ),
    ("workflow", WorkflowConfig, WorkflowSettingsModel, "workflow"),
    ("input", InputConfig, InputSettingsModel, "input"),
    ("output", OutputConfig, OutputSettingsModel, "output"),
    (
        "group_analysis",
        GroupAnalysisConfig,
        GroupAnalysisSettingsModel,
        "group_analysis",
    ),
    ("metadata", MetadataConfig, MetadataSettingsModel, "metadata"),
)


def test_ownership_invariant_unchanged() -> None:
    assert_ownership_invariant_unchanged()


@pytest.mark.parametrize(
    "attr,cls,model_cls,_section",
    _ROOT_CASES,
    ids=[c[0] for c in _ROOT_CASES],
)
def test_normalized_parity(attr, cls, model_cls, _section) -> None:
    assert_normalized_defaults_parity(asdict(cls()), model_cls().model_dump())


@pytest.mark.parametrize(
    "attr,cls,model_cls,_section",
    _ROOT_CASES,
    ids=[c[0] for c in _ROOT_CASES],
)
def test_owned_kwargs_raise(attr, cls, model_cls, _section) -> None:
    field_name = next(iter(model_cls.model_fields))
    with pytest.raises(TypeError):
        cls(**{field_name: object()})


@pytest.mark.parametrize(
    "attr,cls,model_cls,_section",
    _ROOT_CASES,
    ids=[c[0] for c in _ROOT_CASES],
)
def test_mutable_independence(attr, cls, model_cls, _section) -> None:
    assert_mutable_container_independence(cls)


def test_speaker_gate_parity_and_kwargs() -> None:
    assert_normalized_defaults_parity(
        asdict(SpeakerGateConfig()), SpeakerGateSettingsModel().model_dump()
    )
    with pytest.raises(TypeError):
        SpeakerGateConfig(threshold_value=1.0)
    assert_mutable_container_independence(SpeakerGateConfig)


def test_dashboard_dual_pilot_hydrate_and_kwargs() -> None:
    with without_transcriptx_env():
        dash = DashboardConfig()
    display = DashboardDisplaySettingsModel().model_dump()
    overview = DashboardOverviewSettingsModel().model_dump()
    for key, value in display.items():
        assert getattr(dash, key) == value
    for key, value in overview.items():
        assert getattr(dash, key) == value
    with pytest.raises(TypeError):
        DashboardConfig(schema_version=99)
    with pytest.raises(TypeError):
        DashboardConfig(duration_summary_style="compact")
    assert_mutable_container_independence(DashboardConfig)


def test_llm_file_and_env_override(tmp_path: Path) -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
    path = tmp_path / "c.json"
    path.write_text(
        json.dumps({"llm": {"enabled": True, "provider": "ollama"}}),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(path))
    assert cfg.llm.enabled is True
    assert cfg.llm.provider == "ollama"
    # Sibling field untouched
    assert cfg.llm.seed == LLMSettingsModel().seed

    os.environ["TRANSCRIPTX_LLM_MODEL"] = "test-model:tag"
    try:
        apply_transcriptx_env(cfg)
        assert cfg.llm.model == "test-model:tag"
    finally:
        del os.environ["TRANSCRIPTX_LLM_MODEL"]


def test_logging_file_override(tmp_path: Path) -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"logging": {"level": "DEBUG"}}), encoding="utf-8")
    load_config_file_into(cfg, str(path))
    assert cfg.logging.level == "DEBUG"
    assert cfg.logging.backup_count == LoggingSettingsModel().backup_count


def test_dashboard_file_partial_override(tmp_path: Path) -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
    default_style = cfg.dashboard.duration_summary_style
    path = tmp_path / "c.json"
    path.write_text(
        json.dumps({"dashboard": {"duration_hours_threshold_seconds": 7200}}),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(path))
    assert cfg.dashboard.duration_hours_threshold_seconds == 7200
    assert cfg.dashboard.duration_summary_style == default_style


def test_workflow_file_override_scalar(tmp_path: Path) -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
    path = tmp_path / "c.json"
    path.write_text(
        json.dumps({"workflow": {"timeout_quick_seconds": 99}}),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(path))
    assert cfg.workflow.timeout_quick_seconds == 99


def test_all_root_fields_init_false() -> None:
    for _attr, cls, _model, _section in _ROOT_CASES:
        for f in fields(cls):
            assert f.init is False, f"{cls.__name__}.{f.name}"
    for f in fields(DashboardConfig):
        assert f.init is False
    for f in fields(SpeakerGateConfig):
        assert f.init is False
