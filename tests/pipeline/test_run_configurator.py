"""Unit tests for RunConfigurator resolve/apply and draft-clear lifecycle."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from transcriptx.core.pipeline.contracts import RunConfigSnapshot
from transcriptx.core.pipeline.run_configurator import RunConfigurator


@pytest.mark.unit
def test_resolve_and_apply_default_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = object()
    resolved = SimpleNamespace(
        effective_config=cfg,
        effective_dict_nested={"analysis": {}},
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.load_draft_override",
        lambda: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.resolve_effective_config",
        lambda run_dir: resolved,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.validate_config",
        lambda _d: {},
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.save_run_effective",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.compute_config_hash",
        lambda _d: "hash-default",
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.load_project_config",
        lambda: None,
    )
    set_config = MagicMock()
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.set_config",
        set_config,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.CONFIG_SCHEMA_VERSION",
        7,
    )

    result = RunConfigurator().resolve_and_apply(tmp_path)
    assert result.config is cfg
    assert result.draft_override is None
    assert isinstance(result.snapshot, RunConfigSnapshot)
    assert result.snapshot.config_hash == "hash-default"
    assert result.snapshot.config_source == "default"
    assert result.snapshot.draft_override_applied is False
    assert result.snapshot.schema_version == 7
    set_config.assert_called_once_with(cfg)


@pytest.mark.unit
def test_resolve_and_apply_draft_override_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    draft = {"analysis": {"x": 1}, "activation": {"secret": True}}
    resolved = SimpleNamespace(
        effective_config=object(),
        effective_dict_nested={"analysis": {"x": 1}},
    )
    saved_overrides: list = []

    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.load_draft_override",
        lambda: draft,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.strip_activation_keys_from_nested_map",
        lambda d: {"analysis": d["analysis"]},
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.save_run_override",
        lambda run_dir, payload: saved_overrides.append((run_dir, payload)),
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.resolve_effective_config",
        lambda run_dir: resolved,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.validate_config",
        lambda _d: {},
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.save_run_effective",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.compute_config_hash",
        lambda _d: "hash-override",
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.set_config",
        lambda _c: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.CONFIG_SCHEMA_VERSION",
        1,
    )

    result = RunConfigurator().resolve_and_apply(tmp_path)
    assert result.snapshot.config_source == "run_override"
    assert result.snapshot.draft_override_applied is True
    assert result.draft_override == draft
    assert saved_overrides == [(tmp_path, {"analysis": {"x": 1}})]


@pytest.mark.unit
def test_resolve_and_apply_project_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolved = SimpleNamespace(
        effective_config=object(),
        effective_dict_nested={},
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.load_draft_override",
        lambda: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.resolve_effective_config",
        lambda run_dir: resolved,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.validate_config",
        lambda _d: {},
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.save_run_effective",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.compute_config_hash",
        lambda _d: "hash-project",
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.load_project_config",
        lambda: {"project": True},
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.set_config",
        lambda _c: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.CONFIG_SCHEMA_VERSION",
        1,
    )
    result = RunConfigurator().resolve_and_apply(tmp_path)
    assert result.snapshot.config_source == "project"


@pytest.mark.unit
def test_resolve_and_apply_raises_on_validation_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from transcriptx.core.config.validation import ValidationError

    resolved = SimpleNamespace(
        effective_config=object(),
        effective_dict_nested={"analysis": {"x": "bad"}},
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.load_draft_override",
        lambda: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.resolve_effective_config",
        lambda run_dir: resolved,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.validate_config",
        lambda _d: {
            "analysis.x": [ValidationError(field="analysis.x", message="bad type")]
        },
    )
    with pytest.raises(ValueError, match="Configuration validation failed"):
        RunConfigurator().resolve_and_apply(tmp_path)


@pytest.mark.unit
def test_clear_draft_override_respects_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    clear = MagicMock()
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_configurator.clear_draft_override",
        clear,
    )
    cfg = RunConfigurator()
    cfg.clear_draft_override(False)
    clear.assert_not_called()
    cfg.clear_draft_override(True)
    clear.assert_called_once_with()
