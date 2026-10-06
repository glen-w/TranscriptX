"""WhisperX Docker transcription provider (host-orchestrated)."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.app.models.results import TranscriptionProviderResult
from transcriptx.core.utils.paths import PATHS
from transcriptx.services.transcription.env import get_secret, load_merged_env
from transcriptx.services.transcription.provider import (
    ProviderAvailability,
    ProviderCheck,
    ProviderInfo,
)
from transcriptx.services.transcription.redact import redact_secret, tail_lines

_PROVIDER_ID = "whisperx_docker"
_RECIPE_PATH = PATHS.project_root / "docs" / "recipes" / "whisperx" / "README.md"
_DEFAULT_IMAGE = "ghcr.io/m-bain/whisperx:latest"
_TAIL_LINES = 20


def resolve_docker_binary() -> Path | None:
    found = shutil.which("docker")
    return Path(found) if found else None


def _discover_json(output_dir: Path, audio_stem: str, started_at: float) -> Path | None:
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


def _docker_daemon_ok(binary: Path) -> tuple[bool, str | None]:
    try:
        proc = subprocess.run(
            [str(binary), "info"],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except subprocess.TimeoutExpired:
        return False, "docker info timed out"
    except OSError as exc:
        return False, str(exc)
    if proc.returncode != 0:
        return False, "docker daemon is not reachable"
    return True, None


class WhisperXDockerProvider:
    provider_id = _PROVIDER_ID

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=_PROVIDER_ID,
            label="WhisperX (Docker)",
            description="Host-orchestrated WhisperX via docker run (CUDA or CPU).",
        )

    @property
    def recipe_path(self) -> Path:
        return _RECIPE_PATH

    def is_available(self, options: TranscriptionOptions) -> ProviderAvailability:
        checks: list[ProviderCheck] = []
        merged = load_merged_env()
        binary = resolve_docker_binary()
        checks.append(
            ProviderCheck(
                key="docker",
                label="docker binary",
                passed=binary is not None,
                message=(
                    None if binary is not None else "Install Docker and add it to PATH"
                ),
            )
        )
        daemon_ok = False
        daemon_msg = "docker not found"
        if binary is not None:
            daemon_ok, daemon_msg = _docker_daemon_ok(binary)
        checks.append(
            ProviderCheck(
                key="docker_daemon",
                label="docker daemon",
                passed=daemon_ok,
                message=None if daemon_ok else daemon_msg,
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
        binary = resolve_docker_binary()
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
                error="docker binary not found",
            )

        audio_path = audio_path.resolve()
        output_dir = output_dir.resolve()
        image = (options.docker_image or "").strip() or _DEFAULT_IMAGE
        cmd = [str(binary), "run", "--rm"]
        if options.device == "cuda":
            cmd.extend(["--gpus", "all"])
        cmd.extend(
            [
                "-v",
                f"{audio_path.parent}:/audio:ro",
                "-v",
                f"{output_dir}:/output",
            ]
        )
        proc_env = os.environ.copy()
        if token:
            proc_env["HF_TOKEN"] = token
            cmd.extend(["-e", "HF_TOKEN"])
        cmd.extend(
            [
                image,
                "whisperx",
                f"/audio/{audio_path.name}",
                "--output_dir",
                "/output",
                "--model",
                options.model,
                "--language",
                options.language,
                "--device",
                options.device,
                "--compute_type",
                options.compute_type,
                "--batch_size",
                str(options.batch_size),
            ]
        )
        if options.diarize:
            cmd.append("--diarize")
        if options.min_speakers is not None:
            cmd.extend(["--min_speakers", str(int(options.min_speakers))])
        if options.max_speakers is not None:
            cmd.extend(["--max_speakers", str(int(options.max_speakers))])

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
                return TranscriptionProviderResult(
                    success=False,
                    json_path=None,
                    output_dir=output_dir,
                    returncode=proc.returncode,
                    stdout_tail=tail_lines(redact_secret(stdout or "", secrets)),
                    stderr_tail=tail_lines(redact_secret(stderr or "", secrets)),
                    duration_seconds=duration,
                    error="WhisperX Docker timed out",
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
                stdout_tail=tail_lines(stdout_text, max_lines=_TAIL_LINES),
                stderr_tail=tail_lines(stderr_text, max_lines=_TAIL_LINES),
                duration_seconds=duration,
                error=f"docker/whisperx exited with code {proc.returncode}",
            )

        json_path = _discover_json(output_dir, audio_path.stem, started)
        if json_path is None:
            return TranscriptionProviderResult(
                success=False,
                json_path=None,
                output_dir=output_dir,
                returncode=proc.returncode,
                stdout_tail=tail_lines(stdout_text, max_lines=_TAIL_LINES),
                stderr_tail=tail_lines(stderr_text, max_lines=_TAIL_LINES),
                duration_seconds=duration,
                error="No JSON output found after WhisperX Docker run",
            )

        return TranscriptionProviderResult(
            success=True,
            json_path=json_path,
            output_dir=output_dir,
            returncode=proc.returncode,
            stdout_tail=tail_lines(stdout_text, max_lines=_TAIL_LINES),
            stderr_tail=tail_lines(stderr_text, max_lines=_TAIL_LINES),
            duration_seconds=duration,
        )
