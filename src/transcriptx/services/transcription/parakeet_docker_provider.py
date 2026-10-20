"""NeMo Parakeet Docker transcription provider (host-orchestrated, Wave H5)."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.app.models.results import TranscriptionProviderResult
from transcriptx.core.utils.paths import PATHS
from transcriptx.services.transcription.env import load_merged_env
from transcriptx.services.transcription.nemo_json_to_whisperx import convert_file
from transcriptx.services.transcription.provider import (
    ProviderAvailability,
    ProviderCheck,
    ProviderInfo,
)
from transcriptx.services.transcription.redact import tail_lines
from transcriptx.services.transcription.whisperx_docker_provider import (
    _discover_json,
    _docker_daemon_ok,
    resolve_docker_binary,
)

_PROVIDER_ID = "parakeet_docker"
_RECIPE_PATH = PATHS.project_root / "docs" / "recipes" / "parakeet" / "README.md"
_DEFAULT_IMAGE = "nvcr.io/nvidia/nemo:24.07.1"
_TAIL_LINES = 20


def _write_stub_jsonl(output_dir: Path, audio_stem: str) -> Path:
    """Development/CI stub when TRANSCRIPTX_PARAKEET_STUB=1."""
    jsonl_path = output_dir / f"{audio_stem}.jsonl"
    line = json.dumps(
        {"start": 0.0, "end": 1.0, "text": "(Parakeet stub transcript — configure NeMo)"}
    )
    jsonl_path.write_text(line + "\n", encoding="utf-8")
    return jsonl_path


class ParakeetDockerProvider:
    provider_id = _PROVIDER_ID

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=_PROVIDER_ID,
            label="NeMo Parakeet (Docker)",
            description=(
                "Host-orchestrated NeMo Parakeet via docker run (CUDA Linux). "
                "See docs/recipes/parakeet/."
            ),
        )

    @property
    def recipe_path(self) -> Path:
        return _RECIPE_PATH

    def is_available(self, options: TranscriptionOptions) -> ProviderAvailability:
        if os.environ.get("TRANSCRIPTX_PARAKEET_STUB") == "1":
            return ProviderAvailability(
                available=True,
                reason=None,
                checks=(
                    ProviderCheck(
                        key="stub",
                        label="parakeet stub mode",
                        passed=True,
                        message="TRANSCRIPTX_PARAKEET_STUB=1 (no GPU weights)",
                    ),
                ),
            )
        checks: list[ProviderCheck] = []
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
        load_merged_env()
        binary = resolve_docker_binary()
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
        stem = audio_path.stem

        if os.environ.get("TRANSCRIPTX_PARAKEET_STUB") == "1":
            try:
                jsonl_path = _write_stub_jsonl(output_dir, stem)
                json_path = output_dir / f"{stem}.json"
                convert_file(jsonl_path, json_path)
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
                image,
                "bash",
                "-lc",
                (
                    f'echo "Configure NeMo transcribe for {options.model}; '
                    f'see docs/recipes/parakeet/README.md" && exit 2'
                ),
            ]
        )
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=options.timeout_seconds or None,
            )
        except subprocess.TimeoutExpired:
            return TranscriptionProviderResult(
                success=False,
                json_path=None,
                output_dir=output_dir,
                returncode=None,
                stdout_tail=(),
                stderr_tail=(),
                duration_seconds=time.time() - started,
                error="Parakeet Docker timed out",
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
        if proc.returncode != 0:
            return TranscriptionProviderResult(
                success=False,
                json_path=None,
                output_dir=output_dir,
                returncode=proc.returncode,
                stdout_tail=tail_lines(proc.stdout or "", max_lines=_TAIL_LINES),
                stderr_tail=tail_lines(proc.stderr or "", max_lines=_TAIL_LINES),
                duration_seconds=duration,
                error=(
                    "Parakeet Docker not configured — customize NeMo command per "
                    "docs/recipes/parakeet/ (or set TRANSCRIPTX_PARAKEET_STUB=1 for stub)"
                ),
            )

        jsonl_candidates = list(output_dir.glob("*.jsonl"))
        if jsonl_candidates:
            jsonl_path = max(jsonl_candidates, key=lambda p: p.stat().st_mtime)
            json_path = output_dir / f"{stem}.json"
            try:
                convert_file(jsonl_path, json_path)
            except (OSError, ValueError) as exc:
                return TranscriptionProviderResult(
                    success=False,
                    json_path=None,
                    output_dir=output_dir,
                    returncode=proc.returncode,
                    stdout_tail=tail_lines(proc.stdout or "", max_lines=_TAIL_LINES),
                    stderr_tail=tail_lines(proc.stderr or "", max_lines=_TAIL_LINES),
                    duration_seconds=duration,
                    error=f"JSONL convert failed: {exc}",
                )
        else:
            json_path = _discover_json(output_dir, stem, started)

        if json_path is None or not json_path.is_file():
            return TranscriptionProviderResult(
                success=False,
                json_path=None,
                output_dir=output_dir,
                returncode=proc.returncode,
                stdout_tail=tail_lines(proc.stdout or "", max_lines=_TAIL_LINES),
                stderr_tail=tail_lines(proc.stderr or "", max_lines=_TAIL_LINES),
                duration_seconds=duration,
                error="No JSON output found after Parakeet Docker run",
            )

        return TranscriptionProviderResult(
            success=True,
            json_path=json_path,
            output_dir=output_dir,
            returncode=proc.returncode,
            stdout_tail=tail_lines(proc.stdout or "", max_lines=_TAIL_LINES),
            stderr_tail=tail_lines(proc.stderr or "", max_lines=_TAIL_LINES),
            duration_seconds=duration,
        )
