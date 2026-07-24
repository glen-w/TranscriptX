"""Tests for settings persistence contracts."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.config import persistence as config_persistence
from transcriptx.core.config.persistence import (
    clear_draft_override,
    get_run_override_path,
    load_draft_override,
    load_project_config,
    save_draft_override,
    save_project_config,
)
from transcriptx.core.config.resolver import resolve_effective_config


def test_save_project_config_roundtrip_uses_wrapped_payload(
    tmp_path, monkeypatch
) -> None:
    cfg_dir = tmp_path / ".transcriptx"
    monkeypatch.setattr(config_persistence, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_persistence, "CONFIG_DRAFTS_DIR", cfg_dir / "drafts")

    payload = {"output": {"dynamic_charts": "off"}}
    save_project_config(payload)

    raw_path = cfg_dir / "config.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    assert raw["schema_version"] == config_persistence.CONFIG_SCHEMA_VERSION
    assert raw["config"] == payload
    assert load_project_config() == payload


def test_clear_draft_override_removes_file(tmp_path, monkeypatch) -> None:
    cfg_dir = tmp_path / ".transcriptx"
    monkeypatch.setattr(config_persistence, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_persistence, "CONFIG_DRAFTS_DIR", cfg_dir / "drafts")

    save_draft_override({"output": {"dynamic_views": "on"}})
    assert load_draft_override() == {"output": {"dynamic_views": "on"}}
    clear_draft_override()
    assert load_draft_override() is None


def test_get_run_override_path_contract() -> None:
    run_dir = Path("/tmp/transcriptx/outputs/slug/run123")
    assert (
        get_run_override_path(run_dir)
        == run_dir / ".transcriptx" / "run_config_override.json"
    )


def test_resolve_effective_config_uses_draft_when_run_not_selected(
    tmp_path, monkeypatch
) -> None:
    cfg_dir = tmp_path / ".transcriptx"
    monkeypatch.setattr(config_persistence, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_persistence, "CONFIG_DRAFTS_DIR", cfg_dir / "drafts")

    save_draft_override({"output": {"dynamic_views": "off"}})
    resolved = resolve_effective_config(run_dir=None)

    assert resolved.effective_dict_nested["output"]["dynamic_views"] == "off"
    assert resolved.sources_by_key["output.dynamic_views"] == "run"


def test_resolve_effective_config_run_id_derives_run_dir_from_outputs(
    tmp_path, monkeypatch
) -> None:
    # When run_dir is omitted, resolver derives it from OUTPUTS_DIR/run_id.
    outputs_dir = tmp_path / "outputs"
    run_id = "run-7"
    run_dir = outputs_dir / run_id
    run_dir.mkdir(parents=True)
    config_persistence.save_run_override(run_dir, {"logging": {"level": "WARNING"}})

    import transcriptx.core.utils.paths as paths_mod

    monkeypatch.setattr(paths_mod, "OUTPUTS_DIR", outputs_dir)
    resolved = resolve_effective_config(run_id=run_id, run_dir=None)
    assert resolved.effective_dict_nested["logging"]["level"] == "WARNING"
    assert resolved.sources_by_key["logging.level"] == "run"


def test_apply_project_config_to_live_facade_restores_saved_questions(
    tmp_path, monkeypatch
) -> None:
    """Settings → Questions reads get_config(); hydrate must reload disk library."""
    from transcriptx.core.utils.config import get_config, reset_config_for_tests

    cfg_dir = tmp_path / ".transcriptx"
    monkeypatch.setattr(config_persistence, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_persistence, "CONFIG_DRAFTS_DIR", cfg_dir / "drafts")

    payload = {
        "analysis": {
            "llm_custom_qa": {
                "saved_questions": [
                    {
                        "text": "What was decided?",
                        "scopes": {"global": True, "per_speaker": False},
                    }
                ]
            }
        }
    }
    save_project_config(payload)
    reset_config_for_tests()
    assert get_config().analysis.llm_custom_qa.saved_questions == []

    assert config_persistence.apply_project_config_to_live_facade() is True
    live = get_config().analysis.llm_custom_qa.saved_questions
    assert len(live) == 1
    first = live[0]
    text = first["text"] if isinstance(first, dict) else first.text
    assert text == "What was decided?"
    reset_config_for_tests()


def test_apply_project_config_to_live_facade_noop_when_missing(
    tmp_path, monkeypatch
) -> None:
    from transcriptx.core.utils.config import reset_config_for_tests

    cfg_dir = tmp_path / ".transcriptx"
    monkeypatch.setattr(config_persistence, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_persistence, "CONFIG_DRAFTS_DIR", cfg_dir / "drafts")
    reset_config_for_tests()
    assert config_persistence.apply_project_config_to_live_facade() is False
    reset_config_for_tests()
