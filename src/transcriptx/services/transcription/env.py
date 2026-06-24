"""Environment loading for transcription providers."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Mapping

from transcriptx.app.models.requests import (
    TranscriptionConversionOptions,
    TranscriptionOptions,
)
from transcriptx.core.utils.paths import PATHS

_WHISPERX_ENV_CANDIDATES = (
    PATHS.project_root / "whisperx.env",
    PATHS.project_root / "docs" / "recipes" / "whisperx" / "whisperx.env",
)

_LINE_RE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=value / export KEY=value lines from an env file."""
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _LINE_RE.match(line)
        if not match:
            continue
        key, value = match.group(1), _strip_quotes(match.group(2))
        result[key] = value
    return result


def find_whisperx_env_path() -> Path | None:
    for candidate in _WHISPERX_ENV_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


def load_merged_env(overrides: Mapping[str, str] | None = None) -> dict[str, str]:
    """Merge whisperx.env → os.environ → overrides."""
    merged: dict[str, str] = {}
    env_path = find_whisperx_env_path()
    if env_path is not None:
        merged.update(parse_env_file(env_path))
    merged.update({k: v for k, v in os.environ.items() if v is not None})
    if overrides:
        merged.update({k: str(v) for k, v in overrides.items() if v is not None})
    return merged


def parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_int(value: str | None, *, default: int = 0) -> int:
    if value is None or value.strip() == "":
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def get_secret(name: str, env: Mapping[str, str] | None = None) -> str | None:
    merged = env if env is not None else load_merged_env()
    value = merged.get(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def default_transcription_options(
    env: Mapping[str, str] | None = None,
) -> TranscriptionOptions:
    merged = env if env is not None else load_merged_env()
    return TranscriptionOptions(
        provider_id=merged.get("TRANSCRIPTX_TRANSCRIPTION_PROVIDER", "whispermlx"),
        model=merged.get("WHISPERMLX_MODEL", "large-v3"),
        language=merged.get("WHISPERMLX_LANGUAGE", "en"),
        diarize=parse_bool(merged.get("WHISPERMLX_DIARIZE"), default=True),
        timeout_seconds=parse_int(merged.get("WHISPERMLX_TIMEOUT_SECONDS"), default=0),
    )


def default_conversion_options(
    env: Mapping[str, str] | None = None,
) -> TranscriptionConversionOptions:
    merged = env if env is not None else load_merged_env()
    return TranscriptionConversionOptions(
        codec=merged.get("TRANSCRIPTION_MP3_CODEC", "libmp3lame"),
        bitrate=merged.get("TRANSCRIPTION_MP3_BITRATE", "128k"),
        channels=parse_int(merged.get("TRANSCRIPTION_MP3_CHANNELS"), default=2),
        sample_rate=parse_int(merged.get("TRANSCRIPTION_MP3_SAMPLE_RATE"), default=0),
        force_reencode=parse_bool(
            merged.get("TRANSCRIPTION_FORCE_REENCODE"), default=False
        ),
    )


def default_request_flags(env: Mapping[str, str] | None = None) -> dict[str, bool]:
    merged = env if env is not None else load_merged_env()
    return {
        "import_into_library": True,
        "overwrite_import": False,
        "keep_intermediates": parse_bool(
            merged.get("TRANSCRIPTION_KEEP_INTERMEDIATES"), default=False
        ),
    }


def build_transcription_options(
    overrides: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> TranscriptionOptions:
    base = default_transcription_options(env)
    if not overrides:
        return base
    return TranscriptionOptions(
        provider_id=str(overrides.get("provider_id", base.provider_id)),
        model=str(overrides.get("model", base.model)),
        language=str(overrides.get("language", base.language)),
        diarize=bool(overrides.get("diarize", base.diarize)),
        timeout_seconds=int(overrides.get("timeout_seconds", base.timeout_seconds)),
    )
