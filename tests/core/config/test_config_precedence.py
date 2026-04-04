"""Config precedence: defaults → project → run override → env (resolver)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.core.config.persistence import save_run_override
from transcriptx.core.config.resolver import resolve_effective_config


@pytest.mark.unit
def test_resolve_precedence_run_overrides_project(tmp_path: Path) -> None:
    """Run-scoped override wins over project for the same flattened key."""
    project = {"output": {"dynamic_charts": "off"}}
    run_ov = {"output": {"dynamic_charts": "on"}}

    with patch(
        "transcriptx.core.config.resolver.load_project_config", return_value=project
    ):
        with patch(
            "transcriptx.core.config.resolver.load_draft_override", return_value={}
        ):
            save_run_override(tmp_path, run_ov)
            resolved = resolve_effective_config(run_dir=tmp_path)
            eff = resolved.effective_dict_nested
            assert eff.get("output", {}).get("dynamic_charts") == "on"
            flat = resolved.sources_by_key
            assert any(
                k.startswith("output") and flat.get(k) == "run"
                for k in flat
                if "dynamic" in k
            )


@pytest.mark.unit
def test_resolve_env_layer_applied_after_run(monkeypatch, tmp_path: Path) -> None:
    """Env merge is last: any key differing from defaults via env wins."""
    with patch("transcriptx.core.config.resolver.load_project_config", return_value={}):
        with patch(
            "transcriptx.core.config.resolver.load_draft_override", return_value={}
        ):
            save_run_override(tmp_path, {"logging": {"level": "INFO"}})

            def fake_env_overrides(defaults):
                return {"logging.level": "DEBUG"}

            monkeypatch.setattr(
                "transcriptx.core.config.resolver._load_env_overrides",
                fake_env_overrides,
            )
            resolved = resolve_effective_config(run_dir=tmp_path)
            assert (
                resolved.effective_dict_nested.get("logging", {}).get("level")
                == "DEBUG"
            )
            assert resolved.sources_by_key.get("logging.level") == "env"


@pytest.mark.unit
def test_malformed_project_config_ignored_or_empty(monkeypatch, tmp_path: Path) -> None:
    """Missing project file yields defaults + run only."""
    monkeypatch.setattr(
        "transcriptx.core.config.resolver.load_project_config", lambda: {}
    )
    monkeypatch.setattr(
        "transcriptx.core.config.resolver.load_draft_override", lambda: {}
    )
    save_run_override(tmp_path, {"output": {"save_intermediate": True}})
    resolved = resolve_effective_config(run_dir=tmp_path)
    assert (
        resolved.effective_dict_nested.get("output", {}).get("save_intermediate")
        is True
    )
