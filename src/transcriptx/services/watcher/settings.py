"""Directory watcher settings — defaults ← watcher.json ← env."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from transcriptx.core.audio.types import SUPPORTED_AUDIO_EXTENSIONS
from transcriptx.core.utils.paths import CONFIG_DIR, PATHS
from transcriptx.io.import_admission import SUPPORTED_IMPORT_EXTENSIONS

TranscriptMode = Literal["auto_import", "offer", "ignore"]
AudioMode = Literal["offer", "auto_transcribe", "ignore"]
OnSuccessMode = Literal["leave", "mark"]

WATCHER_SETTINGS_FILENAME = "watcher.json"
WATCHER_SETTINGS_SCHEMA_VERSION = 1


def _default_transcript_extensions() -> list[str]:
    return sorted(SUPPORTED_IMPORT_EXTENSIONS)


def _default_audio_extensions() -> list[str]:
    return sorted(SUPPORTED_AUDIO_EXTENSIONS)


class DirectoryWatcherSettings(BaseModel):
    """User-facing watcher configuration (default-off, fail-closed)."""

    schema_version: int = Field(default=WATCHER_SETTINGS_SCHEMA_VERSION)
    enabled: bool = False
    watch_paths: list[str] = Field(default_factory=list)
    recursive: bool = False
    debounce_ms: int = Field(default=2000, ge=100, le=120_000)
    stability_checks: int = Field(default=3, ge=1, le=20)
    stability_interval_ms: int = Field(default=500, ge=50, le=30_000)
    transcript_mode: TranscriptMode = "auto_import"
    audio_mode: AudioMode = "offer"
    extensions_transcript: list[str] = Field(
        default_factory=_default_transcript_extensions
    )
    extensions_audio: list[str] = Field(default_factory=_default_audio_extensions)
    on_success: OnSuccessMode = "leave"
    transcription_profile: str | None = None
    poll_fallback_seconds: float = Field(default=0.0, ge=0.0, le=3600.0)

    @field_validator("watch_paths")
    @classmethod
    def _normalize_paths(cls, value: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for raw in value:
            text = str(raw or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(text)
        return out

    @field_validator("extensions_transcript", "extensions_audio")
    @classmethod
    def _normalize_extensions(cls, value: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for raw in value:
            ext = str(raw or "").strip().lower()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = f".{ext}"
            if ext in seen:
                continue
            seen.add(ext)
            out.append(ext)
        return out

    def validate_for_enable(self) -> list[str]:
        """Return user-safe validation errors when enabling the watcher."""
        errors: list[str] = []
        if not self.watch_paths:
            errors.append("At least one absolute watch path is required when enabled.")
        for path_text in self.watch_paths:
            expanded = Path(path_text).expanduser()
            if not expanded.is_absolute():
                errors.append(f"Watch path must be absolute: {path_text}")
        if self.audio_mode == "auto_transcribe":
            errors.append(
                "audio_mode=auto_transcribe requires a host STT provider "
                "(theme H); use offer or ignore until then."
            )
        return errors


def watcher_settings_path(*, config_dir: Path | None = None) -> Path:
    root = Path(config_dir) if config_dir is not None else Path(CONFIG_DIR)
    return root / WATCHER_SETTINGS_FILENAME


def _parse_bool(raw: str) -> bool | None:
    text = raw.strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def _parse_path_list(raw: str) -> list[str]:
    text = raw.strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(p).strip() for p in parsed if str(p).strip()]
        except json.JSONDecodeError:
            pass
    return [part.strip() for part in text.split(os.pathsep) if part.strip()]


def _apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    mapping: dict[str, str] = {
        "TRANSCRIPTX_WATCHER_ENABLED": "enabled",
        "TRANSCRIPTX_WATCHER_PATHS": "watch_paths",
        "TRANSCRIPTX_WATCHER_RECURSIVE": "recursive",
        "TRANSCRIPTX_WATCHER_DEBOUNCE_MS": "debounce_ms",
        "TRANSCRIPTX_WATCHER_STABILITY_CHECKS": "stability_checks",
        "TRANSCRIPTX_WATCHER_STABILITY_INTERVAL_MS": "stability_interval_ms",
        "TRANSCRIPTX_WATCHER_TRANSCRIPT_MODE": "transcript_mode",
        "TRANSCRIPTX_WATCHER_AUDIO_MODE": "audio_mode",
        "TRANSCRIPTX_WATCHER_ON_SUCCESS": "on_success",
        "TRANSCRIPTX_WATCHER_TRANSCRIPTION_PROFILE": "transcription_profile",
        "TRANSCRIPTX_WATCHER_POLL_FALLBACK_SECONDS": "poll_fallback_seconds",
    }
    out = dict(data)
    for env_name, field in mapping.items():
        raw = os.environ.get(env_name)
        if raw is None or not str(raw).strip():
            continue
        if field == "enabled" or field == "recursive":
            parsed = _parse_bool(raw)
            if parsed is not None:
                out[field] = parsed
        elif field == "watch_paths":
            out[field] = _parse_path_list(raw)
        elif field in {
            "debounce_ms",
            "stability_checks",
            "stability_interval_ms",
        }:
            try:
                out[field] = int(str(raw).strip(), 10)
            except ValueError:
                continue
        elif field == "poll_fallback_seconds":
            try:
                out[field] = float(str(raw).strip())
            except ValueError:
                continue
        elif field == "transcription_profile":
            out[field] = str(raw).strip() or None
        else:
            out[field] = str(raw).strip()
    return out


def load_watcher_settings(
    *, config_dir: Path | None = None
) -> DirectoryWatcherSettings:
    """Load settings: defaults ← watcher.json ← env."""
    path = watcher_settings_path(config_dir=config_dir)
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, json.JSONDecodeError):
            data = {}
    data = _apply_env_overrides(data)
    return DirectoryWatcherSettings.model_validate(data)


def save_watcher_settings(
    settings: DirectoryWatcherSettings,
    *,
    config_dir: Path | None = None,
) -> Path:
    """Persist settings to config_dir/watcher.json (atomic replace)."""
    path = watcher_settings_path(config_dir=config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = settings.model_dump()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    tmp.replace(path)
    return path


def default_jobs_dir(*, data_dir: Path | None = None) -> Path:
    root = Path(data_dir) if data_dir is not None else Path(PATHS.data_dir)
    return root / "watcher" / "jobs"
