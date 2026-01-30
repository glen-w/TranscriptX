"""Config resolution for effective settings with provenance."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Optional
import json
import os
import tempfile

from transcriptx.core.utils.config import TranscriptXConfig

from .registry import flatten, unflatten, get_default_config_dict
from .persistence import (
    load_project_config,
    load_draft_override,
    load_run_override,
)


SourceLabel = Literal["default", "project", "run", "env"]


@dataclass(frozen=True)
class ResolvedConfig:
    effective_config: TranscriptXConfig
    sources_by_key: Dict[str, SourceLabel]
    effective_dict_nested: Dict[str, Any]
    effective_dotmap: Dict[str, Any]


def _without_env_prefix(prefix: str) -> Dict[str, Optional[str]]:
    removed: Dict[str, Optional[str]] = {}
    for key in list(os.environ.keys()):
        if key.startswith(prefix):
            removed[key] = os.environ.pop(key)
    return removed


def _restore_env(removed: Dict[str, Optional[str]]) -> None:
    for key, value in removed.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _build_config_from_dict(config_dict: Dict[str, Any]) -> TranscriptXConfig:
    removed = _without_env_prefix("TRANSCRIPTX_")
    tmp_path = None
    try:
        config = TranscriptXConfig()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as handle:
            json.dump(config_dict, handle, indent=2)
            tmp_path = handle.name
        config._load_from_file(tmp_path)
        return config
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        _restore_env(removed)


def _load_env_overrides(defaults: Dict[str, Any]) -> Dict[str, Any]:
    config_with_env = TranscriptXConfig()
    env_dot = flatten(config_with_env.to_dict())
    default_dot = flatten(defaults)
    env_overrides: Dict[str, Any] = {}
    for key, value in env_dot.items():
        if key not in default_dot or default_dot[key] != value:
            env_overrides[key] = value
    return env_overrides


def resolve_effective_config(
    run_id: Optional[str] = None, run_dir: Optional[Path] = None
) -> ResolvedConfig:
    """Resolve effective config and provenance for a run or draft override."""
    defaults = get_default_config_dict()
    effective_dot = flatten(defaults)
    sources: Dict[str, SourceLabel] = {key: "default" for key in effective_dot}

    project = load_project_config() or {}
    project_dot = flatten(project)
    for key, value in project_dot.items():
        effective_dot[key] = value
        sources[key] = "project"

    if run_id is None and run_dir is None:
        run_override = load_draft_override() or {}
    else:
        from transcriptx.core.utils.paths import OUTPUTS_DIR

        if run_dir is None:
            run_dir = Path(OUTPUTS_DIR) / str(run_id)
        run_override = load_run_override(run_dir) or {}

    run_dot = flatten(run_override)
    for key, value in run_dot.items():
        effective_dot[key] = value
        sources[key] = "run"

    env_dot = _load_env_overrides(defaults)
    for key, value in env_dot.items():
        effective_dot[key] = value
        sources[key] = "env"

    effective_nested = unflatten(effective_dot)
    effective_config = _build_config_from_dict(effective_nested)
    return ResolvedConfig(
        effective_config=effective_config,
        sources_by_key=sources,
        effective_dict_nested=effective_nested,
        effective_dotmap=effective_dot,
    )
