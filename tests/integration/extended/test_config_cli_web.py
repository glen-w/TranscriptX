"""Integration tests for CLI and web config compatibility."""

import json

from transcriptx.core.config import (
    load_project_config,
    resolve_effective_config,
    save_project_config,
)
from transcriptx.core.config import persistence as config_persistence
from transcriptx.core.utils.config import TranscriptXConfig


def test_cli_config_round_trip_into_web_config(tmp_path, monkeypatch):
    monkeypatch.setattr(config_persistence, "CONFIG_DIR", tmp_path / ".transcriptx")
    monkeypatch.setattr(
        config_persistence,
        "CONFIG_DRAFTS_DIR",
        config_persistence.CONFIG_DIR / "drafts",
    )

    config = TranscriptXConfig()
    config.dashboard.overview_max_items = 5

    cli_path = tmp_path / "cli_config.json"
    config.save_to_file(str(cli_path))
    payload = json.loads(cli_path.read_text())

    save_project_config(payload)
    project = load_project_config()

    assert project["dashboard"]["overview_max_items"] == 5

    resolved = resolve_effective_config()
    assert resolved.effective_config.dashboard.overview_max_items == 5


def test_web_config_resolves_to_transcriptx_config(tmp_path, monkeypatch):
    monkeypatch.setattr(config_persistence, "CONFIG_DIR", tmp_path / ".transcriptx")
    monkeypatch.setattr(
        config_persistence,
        "CONFIG_DRAFTS_DIR",
        config_persistence.CONFIG_DIR / "drafts",
    )

    config = TranscriptXConfig()
    config.output.dynamic_charts = "off"

    save_project_config(config.to_dict())
    resolved = resolve_effective_config()

    assert resolved.effective_config.output.dynamic_charts == "off"
