import os

import transcriptx.core.config.persistence as persistence
from transcriptx.core.config.registry import flatten, unflatten, get_default_config_dict
from transcriptx.core.config.resolver import resolve_effective_config


def test_golden_config_roundtrip(tmp_path, monkeypatch):
    config_dir = tmp_path / ".transcriptx"
    drafts_dir = config_dir / "drafts"
    monkeypatch.setattr(persistence, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(persistence, "CONFIG_DRAFTS_DIR", drafts_dir)

    # Clear env overrides for deterministic defaults
    for key in list(os.environ.keys()):
        if key.startswith("TRANSCRIPTX_"):
            monkeypatch.delenv(key, raising=False)

    defaults = get_default_config_dict()
    persistence.save_project_config(defaults)

    resolved = resolve_effective_config(run_id=None)
    assert resolved.effective_dict_nested == defaults

    dotmap = flatten(defaults)
    rebuilt = unflatten(dotmap)
    assert rebuilt == defaults
