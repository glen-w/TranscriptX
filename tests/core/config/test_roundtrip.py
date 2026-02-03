from __future__ import annotations

import os
from typing import Any

import transcriptx.core.config.persistence as persistence  # type: ignore[import-untyped]
from transcriptx.core.config.registry import (  # type: ignore[import-untyped]
    flatten,
    get_default_config_dict,
    unflatten,
)
from transcriptx.core.config.resolver import resolve_effective_config  # type: ignore[import-untyped]


def test_golden_config_roundtrip(tmp_path: Any, monkeypatch: Any) -> None:
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
    # Resolver may normalize/coerce some values (e.g., ranges) while preserving semantics.
    # Contract: project defaults should survive resolution for core top-level keys.
    assert resolved.effective_dict_nested["active_workflow_profile"] == defaults["active_workflow_profile"]
    assert resolved.effective_dict_nested["analysis"]["analysis_mode"] == defaults["analysis"]["analysis_mode"]

    dotmap = flatten(defaults)
    rebuilt = unflatten(dotmap)
    assert rebuilt == defaults
