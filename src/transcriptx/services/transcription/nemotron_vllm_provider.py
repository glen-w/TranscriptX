"""Nemotron 3.5 Transcribe provider (host-orchestrated local vLLM, Theme H5)."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.app.models.results import TranscriptionProviderResult
from transcriptx.core.utils.paths import PATHS
from transcriptx.services.transcription.env import load_merged_env
from transcriptx.services.transcription.nemotron_json_to_whisperx import convert_file
from transcriptx.services.transcription.nemotron_vllm_client import (
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    default_base_url,
    probe_endpoint,
    transcribe_file,
    write_raw_dump,
)
from transcriptx.services.transcription.provider import (
    ProviderAvailability,
    ProviderCheck,
    ProviderInfo,
)

_PROVIDER_ID = "nemotron_vllm"
_RECIPE_PATH = (
    PATHS.project_root / "docs" / "recipes" / "nemotron-transcribe" / "README.md"
)
_STUB_ENV = "TRANSCRIPTX_NEMOTRON_STUB"


def _stub_enabled() -> bool:
    return os.environ.get(_STUB_ENV) == "1"


def _write_stub_dump(output_dir: Path, audio_stem: str) -> Path:
    raw_path = output_dir / f"{audio_stem}.nemotron.json"
    payload = {
        "choices": [
            {
                "message": {
                    "content": "(Nemotron stub transcript — start local vLLM)",
                }
            }
        ]
    }
    write_raw_dump(payload, raw_path)
    return raw_path


def _keywords(options: TranscriptionOptions) -> tuple[str, ...]:
    if not options.keyword_bias_enabled:
        return ()
    return tuple(str(item).strip() for item in options.keywords if str(item).strip())


def resolve_base_url(
    options: TranscriptionOptions, env: dict[str, str] | None = None
) -> str:
    override = str(getattr(options, "base_url", "") or "").strip()
    if override:
        return override
    return default_base_url(env)


class NemotronVllmProvider:
    provider_id = _PROVIDER_ID

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=_PROVIDER_ID,
            label="Nemotron 3.5 Transcribe (local vLLM)",
            description=(
                "Host-orchestrated NVIDIA Nemotron 3.5 Transcribe via a local "
                "OpenAI-compatible vLLM/NIM server (CUDA). "
                "See docs/recipes/nemotron-transcribe/."
            ),
        )

    @property
    def recipe_path(self) -> Path:
        return _RECIPE_PATH

    def is_available(self, options: TranscriptionOptions) -> ProviderAvailability:
        if _stub_enabled():
            return ProviderAvailability(
                available=True,
                reason=None,
                checks=(
                    ProviderCheck(
                        key="stub",
                        label="nemotron stub mode",
                        passed=True,
                        message=f"{_STUB_ENV}=1 (no GPU weights)",
                    ),
                ),
            )
        checks: list[ProviderCheck] = []
        darwin = sys.platform == "darwin"
        checks.append(
            ProviderCheck(
                key="platform",
                label="CUDA Linux host",
                passed=not darwin,
                message=(
                    None
                    if not darwin
                    else "On macOS prefer whispermlx or Granite; "
                    "run Nemotron Copy command on a CUDA machine."
                ),
            )
        )
        env = load_merged_env()
        url = resolve_base_url(options, env)
        reachable, message = probe_endpoint(url, env=env)
        checks.append(
            ProviderCheck(
                key="endpoint",
                label="local vLLM endpoint",
                passed=reachable,
                message=None if reachable else message,
            )
        )
        available = all(c.passed for c in checks)
        reason = None
        if not available:
            failed = [c for c in checks if not c.passed]
            reason = failed[0].message or failed[0].label
        return ProviderAvailability(
            available=available, reason=reason, checks=tuple(checks)
        )

    def transcribe(
        self,
        audio_path: Path,
        output_dir: Path,
        options: TranscriptionOptions,
    ) -> TranscriptionProviderResult:
        started = time.time()
        output_dir.mkdir(parents=True, exist_ok=True)
        env = load_merged_env()
        audio_path = audio_path.resolve()
        output_dir = output_dir.resolve()
        stem = audio_path.stem
        json_path = output_dir / f"{stem}.json"

        if _stub_enabled():
            try:
                raw_path = _write_stub_dump(output_dir, stem)
                convert_file(raw_path, json_path)
                return TranscriptionProviderResult(
                    success=True,
                    json_path=json_path,
                    output_dir=output_dir,
                    returncode=0,
                    stdout_tail=(),
                    stderr_tail=(),
                    duration_seconds=time.time() - started,
                )
            except OSError as exc:
                return TranscriptionProviderResult(
                    success=False,
                    json_path=None,
                    output_dir=output_dir,
                    returncode=None,
                    stdout_tail=(),
                    stderr_tail=(),
                    duration_seconds=time.time() - started,
                    error=str(exc),
                )

        url = resolve_base_url(options, env)
        model = (options.model or "").strip() or DEFAULT_MODEL
        timeout = options.timeout_seconds or DEFAULT_TIMEOUT_SECONDS
        try:
            dump = transcribe_file(
                audio_path,
                base_url=url,
                model=model,
                diarize=bool(options.diarize),
                keywords=_keywords(options),
                timeout_seconds=timeout,
                env=env,
            )
            raw_path = output_dir / f"{stem}.nemotron.json"
            write_raw_dump(dump, raw_path)
            convert_file(raw_path, json_path)
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            return TranscriptionProviderResult(
                success=False,
                json_path=None,
                output_dir=output_dir,
                returncode=None,
                stdout_tail=(),
                stderr_tail=(str(exc),),
                duration_seconds=time.time() - started,
                error=str(exc),
            )
        return TranscriptionProviderResult(
            success=True,
            json_path=json_path,
            output_dir=output_dir,
            returncode=0,
            stdout_tail=(),
            stderr_tail=(),
            duration_seconds=time.time() - started,
        )
