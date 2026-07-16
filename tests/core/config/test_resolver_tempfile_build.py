"""Resolver tempfile build: env strip, cleanup, and real env precedence."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.core.config.persistence import save_run_override
from transcriptx.core.config.resolver import (
    _build_config_from_dict,
    resolve_effective_config,
)


@pytest.mark.unit
def test_build_config_from_dict_loads_nested_values() -> None:
    cfg = _build_config_from_dict(
        {
            "logging": {"level": "ERROR"},
            "output": {"dynamic_charts": "off"},
        }
    )
    assert cfg.logging.level == "ERROR"
    assert cfg.output.dynamic_charts == "off"


@pytest.mark.unit
def test_build_config_strips_env_during_load_and_restores(monkeypatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_LOG_LEVEL", "CRITICAL")
    monkeypatch.setenv("TRANSCRIPTX_LLM_PROVIDER", "anthropic")
    seen_during_load: dict[str, bool] = {}

    real_load = None

    def _tracking_load(self, path: str) -> None:
        seen_during_load["log"] = "TRANSCRIPTX_LOG_LEVEL" not in os.environ
        seen_during_load["llm"] = "TRANSCRIPTX_LLM_PROVIDER" not in os.environ
        return real_load(self, path)

    from transcriptx.core.utils.config import TranscriptXConfig

    real_load = TranscriptXConfig._load_from_file
    with patch.object(TranscriptXConfig, "_load_from_file", _tracking_load):
        cfg = _build_config_from_dict({"logging": {"level": "WARNING"}})

    assert seen_during_load["log"] is True
    assert seen_during_load["llm"] is True
    assert os.environ.get("TRANSCRIPTX_LOG_LEVEL") == "CRITICAL"
    assert os.environ.get("TRANSCRIPTX_LLM_PROVIDER") == "anthropic"
    # File value applied while env was stripped (not CRITICAL from env)
    assert cfg.logging.level == "WARNING"


@pytest.mark.unit
def test_tempfile_unlinked_on_success(tmp_path: Path, monkeypatch) -> None:
    created: list[str] = []
    import tempfile as tf

    real_named = tf.NamedTemporaryFile

    def _capture(*args, **kwargs):
        handle = real_named(*args, **kwargs)
        created.append(handle.name)
        return handle

    monkeypatch.setattr(
        "transcriptx.core.config.resolver.tempfile.NamedTemporaryFile", _capture
    )
    _build_config_from_dict({"logging": {"level": "INFO"}})
    assert created
    assert not os.path.exists(created[0])


@pytest.mark.unit
def test_tempfile_unlinked_on_failure(monkeypatch) -> None:
    created: list[str] = []
    import tempfile as tf

    real_named = tf.NamedTemporaryFile

    def _capture(*args, **kwargs):
        handle = real_named(*args, **kwargs)
        created.append(handle.name)
        return handle

    monkeypatch.setattr(
        "transcriptx.core.config.resolver.tempfile.NamedTemporaryFile", _capture
    )

    from transcriptx.core.utils.config import TranscriptXConfig

    def _boom(self, path: str) -> None:
        raise RuntimeError("load failed")

    monkeypatch.setattr(TranscriptXConfig, "_load_from_file", _boom)
    with pytest.raises(RuntimeError, match="load failed"):
        _build_config_from_dict({"logging": {"level": "INFO"}})
    assert created
    assert not os.path.exists(created[0])


@pytest.mark.unit
def test_real_env_wins_over_project_and_run(monkeypatch, tmp_path: Path) -> None:
    """defaults < project < run < env for one leaf with real TRANSCRIPTX_* vars."""
    monkeypatch.setenv("TRANSCRIPTX_LOG_LEVEL", "ERROR")
    project = {"logging": {"level": "INFO"}}
    run_ov = {"logging": {"level": "DEBUG"}}

    with patch(
        "transcriptx.core.config.resolver.load_project_config", return_value=project
    ):
        with patch(
            "transcriptx.core.config.resolver.load_draft_override", return_value={}
        ):
            save_run_override(tmp_path, run_ov)
            resolved = resolve_effective_config(run_dir=tmp_path)

    assert resolved.effective_dict_nested["logging"]["level"] == "ERROR"
    assert resolved.sources_by_key.get("logging.level") == "env"
    assert resolved.effective_config.logging.level == "ERROR"
