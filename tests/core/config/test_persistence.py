import transcriptx.core.config.persistence as persistence
from transcriptx.core.utils.config.main import TranscriptXConfig as MainConfig


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


def test_save_config_atomic_failure_preserves_last_valid_artifact(
    tmp_path, monkeypatch
):
    config_dir = tmp_path / ".transcriptx"
    drafts_dir = config_dir / "drafts"
    monkeypatch.setattr(persistence, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(persistence, "CONFIG_DRAFTS_DIR", drafts_dir)

    target = persistence.get_project_config_path()
    persistence.save_project_config({"analysis": {"sentiment_window_size": 10}})
    before = target.read_text(encoding="utf-8")

    def _raise_dump(*_args, **_kwargs):
        raise OSError("simulated write failure")

    monkeypatch.setattr(persistence.json, "dump", _raise_dump)
    try:
        persistence.save_project_config({"analysis": {"sentiment_window_size": 77}})
    except OSError:
        pass

    after = target.read_text(encoding="utf-8")
    assert before == after
    leftovers = list(target.parent.glob(".config_tmp_*.json"))
    assert leftovers == []


def test_main_config_save_to_file_uses_atomic_persistence(tmp_path, monkeypatch):
    target = tmp_path / "config.json"
    cfg = MainConfig()
    cfg.save_to_file(str(target))
    before = target.read_text(encoding="utf-8")

    def _raise_dump(*_args, **_kwargs):
        raise OSError("simulated write failure")

    monkeypatch.setattr(persistence.json, "dump", _raise_dump)
    try:
        cfg.save_to_file(str(target))
    except OSError:
        pass

    assert target.read_text(encoding="utf-8") == before
