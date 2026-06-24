"""Whisper MLX transcription provider (macOS)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.app.models.results import TranscriptionProviderResult
from transcriptx.core.audio.tools import check_ffmpeg_available
from transcriptx.services.transcription.env import get_secret, load_merged_env
from transcriptx.services.transcription.provider import (
    ProviderAvailability,
    ProviderCheck,
    ProviderInfo,
)
from transcriptx.services.transcription.redact import redact_secret, tail_lines

_PROVIDER_ID = "whispermlx"
_TAIL_LINES = 20


def resolve_whispermlx_binary(env: dict[str, str] | None = None) -> Path | None:
    merged = env if env is not None else load_merged_env()
    configured = merged.get("WHISPERMLX")
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return path
    found = shutil.which("whispermlx")
    return Path(found) if found else None


def _discover_json(
    output_dir: Path, audio_stem: str, started_at: float
) -> Path | None:
    exact = output_dir / f"{audio_stem}.json"
    if exact.is_file():
        return exact
    candidates = [
        p
        for p in output_dir.glob("*.json")
        if p.is_file() and p.stat().st_mtime >= started_at - 0.5
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


class WhisperMLXProvider:
    provider_id = _PROVIDER_ID

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=_PROVIDER_ID,
            label="Whisper MLX (Mac)",
            description="Local Apple MLX transcription via whispermlx.",
        )

    def is_available(self, options: TranscriptionOptions) -> ProviderAvailability:
        checks: list[ProviderCheck] = []
        merged = load_merged_env()

        on_mac = sys.platform == "darwin"
        checks.append(
            ProviderCheck(
                key="platform",
                label="macOS",
                passed=on_mac,
                message=None if on_mac else "whispermlx requires macOS",
            )
        )

        ffmpeg_ok, ffmpeg_err = check_ffmpeg_available()
        checks.append(
            ProviderCheck(
                key="ffmpeg",
                label="ffmpeg",
                passed=ffmpeg_ok,
                message=None if ffmpeg_ok else ffmpeg_err,
            )
        )

        binary = resolve_whispermlx_binary(merged)
        checks.append(
            ProviderCheck(
                key="binary",
                label="whispermlx binary",
                passed=binary is not None,
                message=(
                    None
                    if binary is not None
                    else "Set WHISPERMLX or install whispermlx on PATH"
                ),
            )
        )

        token_required = options.diarize
        token = get_secret("HF_TOKEN", merged) if token_required else None
        if token_required:
            checks.append(
                ProviderCheck(
                    key="hf_token",
                    label="HF token (diarization)",
                    passed=bool(token),
                    message=(
                        None
                        if token
                        else "HF_TOKEN required when diarization is enabled"
                    ),
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
        merged = load_merged_env()
        binary = resolve_whispermlx_binary(merged)
        secrets: list[str] = []
        token = get_secret("HF_TOKEN", merged) if options.diarize else None
        if token:
            secrets.append(token)

        if binary is None:
            return TranscriptionProviderResult(
                success=False,
                json_path=None,
                output_dir=output_dir,
                returncode=None,
                stdout_tail=(),
                stderr_tail=(),
                duration_seconds=0.0,
                error="whispermlx binary not found",
            )

        cmd = [
            str(binary),
            str(audio_path),
            "--output_dir",
            str(output_dir),
            "--language",
            options.language,
            "--model",
            options.model,
        ]
        if options.diarize:
            cmd.append("--diarize")

        proc_env = os.environ.copy()
        if token:
            proc_env["HF_TOKEN"] = token

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=proc_env,
            )
            try:
                stdout, stderr = proc.communicate(
                    timeout=options.timeout_seconds or None
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                duration = time.time() - started
                stderr_text = redact_secret(stderr or "", secrets)
                return TranscriptionProviderResult(
                    success=False,
                    json_path=None,
                    output_dir=output_dir,
                    returncode=proc.returncode,
                    stdout_tail=tail_lines(redact_secret(stdout or "", secrets)),
                    stderr_tail=tail_lines(stderr_text),
                    duration_seconds=duration,
                    error="whispermlx timed out",
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

        duration = time.time() - started
        stdout_text = redact_secret(stdout or "", secrets)
        stderr_text = redact_secret(stderr or "", secrets)

        if proc.returncode != 0:
            return TranscriptionProviderResult(
                success=False,
                json_path=None,
                output_dir=output_dir,
                returncode=proc.returncode,
                stdout_tail=tail_lines(stdout_text),
                stderr_tail=tail_lines(stderr_text),
                duration_seconds=duration,
                error=f"whispermlx exited with code {proc.returncode}",
            )

        json_path = _discover_json(output_dir, audio_path.stem, started)
        if json_path is None:
            return TranscriptionProviderResult(
                success=False,
                json_path=None,
                output_dir=output_dir,
                returncode=proc.returncode,
                stdout_tail=tail_lines(stdout_text),
                stderr_tail=tail_lines(stderr_text),
                duration_seconds=duration,
                error="No JSON output found after whispermlx run",
            )

        return TranscriptionProviderResult(
            success=True,
            json_path=json_path,
            output_dir=output_dir,
            returncode=proc.returncode,
            stdout_tail=tail_lines(stdout_text),
            stderr_tail=tail_lines(stderr_text),
            duration_seconds=duration,
        )
