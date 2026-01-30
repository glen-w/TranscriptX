from pathlib import Path

import transcriptx.core.config.persistence as persistence


def test_save_load_project_config(tmp_path, monkeypatch):
    config_dir = tmp_path / ".transcriptx"
    drafts_dir = config_dir / "drafts"
    monkeypatch.setattr(persistence, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(persistence, "CONFIG_DRAFTS_DIR", drafts_dir)

    payload = {"analysis": {"sentiment_window_size": 12}}
    persistence.save_project_config(payload)
    loaded = persistence.load_project_config()
    assert loaded == payload


def test_draft_override_roundtrip(tmp_path, monkeypatch):
    config_dir = tmp_path / ".transcriptx"
    drafts_dir = config_dir / "drafts"
    monkeypatch.setattr(persistence, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(persistence, "CONFIG_DRAFTS_DIR", drafts_dir)

    payload = {"output": {"base_output_dir": "/tmp"}}
    persistence.save_draft_override(payload)
    loaded = persistence.load_draft_override()
    assert loaded == payload
    persistence.clear_draft_override()
    assert persistence.load_draft_override() is None
