"""Operator defaults for auto-name / auto-link (not voice consent)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from transcriptx.core.utils.paths import PATHS
from transcriptx.io.atomic_json import write_json_atomic

IDENTIFY_SETTINGS_FILENAME = "identify.json"
IDENTIFY_SETTINGS_SCHEMA_VERSION = 1


class IdentifySettings(BaseModel):
    """Ingest defaults used by admit, G2 watcher, and Speaker ID apply."""

    model_config = ConfigDict(extra="ignore")

    schema_version: int = Field(default=IDENTIFY_SETTINGS_SCHEMA_VERSION)
    auto_name: bool = False
    auto_link: bool = False
    style_only_apply: bool = False


def identify_settings_path(*, config_dir: Path | None = None) -> Path:
    root = Path(config_dir) if config_dir is not None else Path(PATHS.config_dir)
    return root / IDENTIFY_SETTINGS_FILENAME


def default_identify_settings() -> IdentifySettings:
    return IdentifySettings()


def load_identify_settings(*, config_dir: Path | None = None) -> IdentifySettings:
    path = identify_settings_path(config_dir=config_dir)
    if not path.is_file():
        return default_identify_settings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_identify_settings()
    if not isinstance(raw, dict):
        return default_identify_settings()
    try:
        return IdentifySettings.model_validate(raw)
    except Exception:
        return default_identify_settings()


def save_identify_settings(
    settings: IdentifySettings, *, config_dir: Path | None = None
) -> None:
    path = identify_settings_path(config_dir=config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, settings.model_dump(mode="python"), indent=2)
