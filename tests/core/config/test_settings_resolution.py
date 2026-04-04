"""Effective config resolution and run override persistence (settings UI alignment)."""

from __future__ import annotations


from transcriptx.core.config import (
    get_default_config_dict,
    load_run_override,
    resolve_effective_config,
    save_project_config,
    save_run_override,
)
from transcriptx.core.config import persistence as config_persistence


def test_no_run_dir_effective_layers_project_over_defaults(tmp_path, monkeypatch):
    """Without run_dir, resolver must merge project over defaults — not defaults-only."""
    monkeypatch.setattr(config_persistence, "CONFIG_DIR", tmp_path / ".transcriptx")
    monkeypatch.setattr(
        config_persistence,
        "CONFIG_DRAFTS_DIR",
        config_persistence.CONFIG_DIR / "drafts",
    )

    defaults = get_default_config_dict()
    default_dc = defaults["output"]["dynamic_charts"]

    save_project_config({"output": {"dynamic_charts": "off"}})
    resolved = resolve_effective_config(run_dir=None)

    assert resolved.effective_dict_nested["output"]["dynamic_charts"] == "off"
    assert default_dc != "off"
    assert resolved.sources_by_key.get("output.dynamic_charts") == "project"


def test_run_override_save_load_roundtrip(tmp_path, monkeypatch):
    run_dir = tmp_path / "out" / "slug" / "run1"
    run_dir.mkdir(parents=True)
    payload = {"output": {"dynamic_charts": "on"}}
    save_run_override(run_dir, payload)
    loaded = load_run_override(run_dir)
    assert loaded == payload
