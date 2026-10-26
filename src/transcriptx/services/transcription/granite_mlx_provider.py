"""IBM Granite Speech transcription via host mlx-audio (macOS).

Engines stay out of the analysis image. Streamlit subprocesses a host Python
that has ``mlx-audio>=0.5.9`` (``MLX_AUDIO_PYTHON``). Stub mode
(``TRANSCRIPTX_GRANITE_STUB=1``) writes placeholder JSON for CI.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.app.models.results import TranscriptionProviderResult
from transcriptx.core.audio.tools import check_ffmpeg_available
from transcriptx.core.utils.paths import PATHS
from transcriptx.services.transcription.env import load_merged_env
from transcriptx.services.transcription.granite_json_to_whisperx import (
    stitch_chunk_payloads,
    to_whisperx_payload,
)
from transcriptx.services.transcription.keyword_lists import (
    MAX_KEYWORDS,
    normalize_keywords,
)
from transcriptx.services.transcription.provider import (
    ProviderAvailability,
    ProviderCheck,
    ProviderInfo,
)
from transcriptx.services.transcription.redact import tail_lines

_PROVIDER_ID = "granite_mlx"
_TAIL_LINES = 20
_RECIPE_PATH = PATHS.project_root / "docs" / "recipes" / "granite-speech" / "README.md"

MODEL_ASR = "ibm-granite/granite-speech-5.0-2b"
MODEL_TURBO = "ibm-granite/granite-speech-5.0-470m-turboctc"
MODEL_SAA = "ibm-granite/granite-speech-4.1-2b-plus"
GRANITE_MODEL_OPTIONS: tuple[str, ...] = (MODEL_ASR, MODEL_TURBO, MODEL_SAA)

CHUNK_ASR_SECONDS = 110
CHUNK_SAA_SECONDS = 300
CHUNK_TURBO_SECONDS = 600
_STUB_ENV = "TRANSCRIPTX_GRANITE_STUB"


def is_turbo_ctc(model_id: str) -> bool:
    """True for encoder-only TurboCTC checkpoints (Apache id or custom turboctc)."""
    return "turboctc" in (model_id or "").lower()


def resolve_granite_model(options: TranscriptionOptions) -> str:
    """Pick 5.0-2b vs Plus unless the operator set Turbo or a custom Granite HF id.

    TurboCTC stays Turbo even when Diarize is on (no speaker attribution).
    """
    raw = (options.model or "").strip()
    if is_turbo_ctc(raw):
        return raw
    lowered = raw.lower()
    if raw in {MODEL_ASR, MODEL_SAA}:
        return MODEL_SAA if options.diarize else MODEL_ASR
    if "granite-speech" in lowered or lowered.startswith("ibm-granite/"):
        return raw
    return MODEL_SAA if options.diarize else MODEL_ASR


def chunk_seconds_for_model(model_id: str, *, diarize: bool) -> int:
    if is_turbo_ctc(model_id):
        return CHUNK_TURBO_SECONDS
    if diarize or model_id == MODEL_SAA:
        return CHUNK_SAA_SECONDS
    return CHUNK_ASR_SECONDS


def effective_keywords(
    options: TranscriptionOptions, *, model_id: str | None = None
) -> tuple[str, ...]:
    resolved = model_id or resolve_granite_model(options)
    if is_turbo_ctc(resolved) or not options.keyword_bias_enabled:
        return ()
    keywords, _warning = normalize_keywords(options.keywords)
    return keywords


def build_gen_kwargs(
    options: TranscriptionOptions,
    *,
    model_id: str | None = None,
    prefix_text: str | None = None,
) -> dict[str, object]:
    """mlx-audio ``--gen-kwargs`` payload (no secrets). Empty for TurboCTC."""
    resolved = model_id or resolve_granite_model(options)
    if is_turbo_ctc(resolved):
        return {}
    kwargs: dict[str, object] = {"language": None}
    if resolved == MODEL_SAA or options.diarize:
        kwargs["task"] = "saa"
    else:
        kwargs["punctuate"] = True
        language = (options.language or "").strip()
        if language and language.lower() not in {"auto", "null"}:
            kwargs["source_language"] = language
    keywords = effective_keywords(options, model_id=resolved)
    if keywords:
        kwargs["hotwords"] = list(keywords[:MAX_KEYWORDS])
    if prefix_text:
        kwargs["prefix_text"] = prefix_text
    return kwargs


def resolve_mlx_audio_python(env: dict[str, str] | None = None) -> str | None:
    merged = env if env is not None else load_merged_env()
    configured = merged.get("MLX_AUDIO_PYTHON") or merged.get("TRANSCRIPTX_MLX_AUDIO")
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return str(path)
        found = shutil.which(configured)
        if found:
            return found
    for candidate in (shutil.which("python3"), shutil.which("python")):
        if candidate and _mlx_audio_importable(candidate):
            return candidate
    return None


def _mlx_audio_importable(python: str) -> bool:
    try:
        proc = subprocess.run(
            [python, "-c", "import mlx_audio"],
            capture_output=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def _stub_enabled() -> bool:
    return os.environ.get(_STUB_ENV) == "1"


def _write_stub_whisperx(
    output_dir: Path,
    audio_stem: str,
    options: TranscriptionOptions,
) -> Path:
    if options.diarize:
        payload = {
            "segments": [
                {
                    "speaker_id": 1,
                    "text": "(Granite stub transcript — configure mlx-audio)",
                }
            ]
        }
    else:
        payload = {"text": "(Granite stub transcript — configure mlx-audio)"}
    segments = stitch_chunk_payloads([(payload, 0.0, 1.0)])
    json_path = output_dir / f"{audio_stem}.json"
    json_path.write_text(
        json.dumps(to_whisperx_payload(segments), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return json_path


def _ffmpeg_bin() -> str | None:
    return shutil.which("ffmpeg")


def _ffprobe_duration(path: Path) -> float | None:
    probe = shutil.which("ffprobe")
    if probe is None:
        return None
    try:
        proc = subprocess.run(
            [
                probe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        return float((proc.stdout or "").strip())
    except ValueError:
        return None


def _chunk_plan(
    duration: float | None, chunk_s: int
) -> list[tuple[float, float | None]]:
    if duration is None or duration <= 0:
        return [(0.0, None)]
    if duration <= chunk_s:
        return [(0.0, duration)]
    plan: list[tuple[float, float]] = []
    start = 0.0
    while start < duration:
        length = min(float(chunk_s), duration - start)
        plan.append((start, length))
        start += length
    return plan


def _extract_chunk(
    ffmpeg: str,
    audio_path: Path,
    dest: Path,
    *,
    start: float,
    length: float | None,
) -> None:
    cmd = [ffmpeg, "-y", "-i", str(audio_path), "-ac", "1", "-ar", "16000"]
    if start > 0:
        cmd.extend(["-ss", f"{start:.3f}"])
    if length is not None:
        cmd.extend(["-t", f"{length:.3f}"])
    cmd.append(str(dest))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    if proc.returncode != 0 or not dest.is_file():
        err = (proc.stderr or proc.stdout or "ffmpeg failed").strip()
        raise RuntimeError(f"ffmpeg chunk failed: {err[-400:]}")


def _discover_chunk_json(output_dir: Path, started_at: float) -> Path | None:
    candidates = [
        path
        for path in output_dir.glob("*.json")
        if path.is_file() and path.stat().st_mtime >= started_at - 0.5
    ]
    if not candidates:
        # mlx-audio may write ``output-path`` without a suffix.
        for path in output_dir.iterdir():
            if path.is_file() and path.stat().st_mtime >= started_at - 0.5:
                if path.suffix.lower() in {"", ".json"}:
                    candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _load_json_payload(path: Path) -> object:
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}


def _prefix_from_payload(payload: object) -> str:
    if isinstance(payload, dict):
        text = payload.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        segments = payload.get("segments")
        if isinstance(segments, list):
            parts = []
            for item in segments:
                if isinstance(item, dict) and item.get("text"):
                    speaker = item.get("speaker_id") or item.get("speaker")
                    body = str(item["text"]).strip()
                    if speaker is not None:
                        parts.append(f"[Speaker {speaker}]: {body}")
                    else:
                        parts.append(body)
            return " ".join(parts).strip()
    if isinstance(payload, str):
        return payload.strip()
    return ""


class GraniteMLXProvider:
    provider_id = _PROVIDER_ID

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=_PROVIDER_ID,
            label="Granite Speech (MLX)",
            description=(
                "Local Apple MLX transcription via mlx-audio "
                "(ibm-granite/granite-speech). Apache-2.0. "
                "See docs/recipes/granite-speech/."
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
                        label="granite stub mode",
                        passed=True,
                        message="TRANSCRIPTX_GRANITE_STUB=1 (no Hub weights)",
                    ),
                ),
            )
        checks: list[ProviderCheck] = []
        on_mac = sys.platform == "darwin"
        checks.append(
            ProviderCheck(
                key="platform",
                label="macOS",
                passed=on_mac,
                message=None if on_mac else "Granite mlx-audio requires macOS",
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
        python = resolve_mlx_audio_python()
        checks.append(
            ProviderCheck(
                key="mlx_audio",
                label="mlx-audio Python",
                passed=python is not None,
                message=(
                    None
                    if python is not None
                    else "Set MLX_AUDIO_PYTHON to a Python with mlx-audio>=0.5.9"
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
        stem = audio_path.stem

        if _stub_enabled():
            try:
                json_path = _write_stub_whisperx(output_dir, stem, options)
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

        python = resolve_mlx_audio_python()
        if python is None:
            return TranscriptionProviderResult(
                success=False,
                json_path=None,
                output_dir=output_dir,
                returncode=None,
                stdout_tail=(),
                stderr_tail=(),
                duration_seconds=0.0,
                error="mlx-audio Python not found (set MLX_AUDIO_PYTHON)",
            )
        ffmpeg = _ffmpeg_bin()
        if ffmpeg is None:
            return TranscriptionProviderResult(
                success=False,
                json_path=None,
                output_dir=output_dir,
                returncode=None,
                stdout_tail=(),
                stderr_tail=(),
                duration_seconds=0.0,
                error="ffmpeg not found",
            )

        model_id = resolve_granite_model(options)
        chunk_s = chunk_seconds_for_model(model_id, diarize=options.diarize)
        duration = _ffprobe_duration(audio_path)
        plan = _chunk_plan(duration, chunk_s)
        chunks_dir = output_dir / f".{stem}_granite_chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)

        collected: list[tuple[object, float, float | None]] = []
        stdout_acc: list[str] = []
        stderr_acc: list[str] = []
        prefix_text = ""
        last_code = 0
        timeout = options.timeout_seconds or None

        try:
            for index, (offset, length) in enumerate(plan):
                if timeout is not None:
                    remaining = timeout - (time.time() - started)
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(
                            "mlx_audio.stt.generate", timeout
                        )
                wav_path = chunks_dir / f"chunk_{index:04d}.wav"
                _extract_chunk(
                    ffmpeg,
                    audio_path,
                    wav_path,
                    start=offset,
                    length=length,
                )
                chunk_out = chunks_dir / f"chunk_{index:04d}_out"
                chunk_out.mkdir(parents=True, exist_ok=True)
                gen_kwargs = build_gen_kwargs(
                    options,
                    model_id=model_id,
                    prefix_text=(
                        None if is_turbo_ctc(model_id) else (prefix_text or None)
                    ),
                )
                cmd = [
                    python,
                    "-m",
                    "mlx_audio.stt.generate",
                    "--model",
                    model_id,
                    "--audio",
                    str(wav_path),
                    "--output-path",
                    str(chunk_out / "transcript"),
                    "--format",
                    "json",
                ]
                if gen_kwargs:
                    cmd.extend(["--gen-kwargs", json.dumps(gen_kwargs)])
                chunk_started = time.time()
                chunk_timeout = None
                if timeout is not None:
                    chunk_timeout = max(1.0, timeout - (time.time() - started))
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=chunk_timeout,
                    check=False,
                )
                last_code = proc.returncode
                stdout_acc.extend((proc.stdout or "").splitlines())
                stderr_acc.extend((proc.stderr or "").splitlines())
                if proc.returncode != 0:
                    return TranscriptionProviderResult(
                        success=False,
                        json_path=None,
                        output_dir=output_dir,
                        returncode=proc.returncode,
                        stdout_tail=tail_lines(
                            "\n".join(stdout_acc), max_lines=_TAIL_LINES
                        ),
                        stderr_tail=tail_lines(
                            "\n".join(stderr_acc), max_lines=_TAIL_LINES
                        ),
                        duration_seconds=time.time() - started,
                        error=(
                            f"mlx-audio exited with code {proc.returncode} "
                            f"(chunk {index + 1}/{len(plan)})"
                        ),
                    )
                raw_path = _discover_chunk_json(chunk_out, chunk_started)
                if raw_path is None:
                    return TranscriptionProviderResult(
                        success=False,
                        json_path=None,
                        output_dir=output_dir,
                        returncode=proc.returncode,
                        stdout_tail=tail_lines(
                            "\n".join(stdout_acc), max_lines=_TAIL_LINES
                        ),
                        stderr_tail=tail_lines(
                            "\n".join(stderr_acc), max_lines=_TAIL_LINES
                        ),
                        duration_seconds=time.time() - started,
                        error=f"No JSON output from mlx-audio (chunk {index + 1})",
                    )
                payload = _load_json_payload(raw_path)
                collected.append((payload, offset, length))
                if not is_turbo_ctc(model_id):
                    next_prefix = _prefix_from_payload(payload)
                    if next_prefix:
                        prefix_text = (
                            f"{prefix_text} {next_prefix}".strip()
                            if prefix_text
                            else next_prefix
                        )
        except subprocess.TimeoutExpired:
            return TranscriptionProviderResult(
                success=False,
                json_path=None,
                output_dir=output_dir,
                returncode=None,
                stdout_tail=tail_lines("\n".join(stdout_acc), max_lines=_TAIL_LINES),
                stderr_tail=tail_lines("\n".join(stderr_acc), max_lines=_TAIL_LINES),
                duration_seconds=time.time() - started,
                error="Granite mlx-audio timed out",
            )
        except (OSError, RuntimeError) as exc:
            return TranscriptionProviderResult(
                success=False,
                json_path=None,
                output_dir=output_dir,
                returncode=None,
                stdout_tail=tail_lines("\n".join(stdout_acc), max_lines=_TAIL_LINES),
                stderr_tail=tail_lines("\n".join(stderr_acc), max_lines=_TAIL_LINES),
                duration_seconds=time.time() - started,
                error=str(exc),
            )

        segments = stitch_chunk_payloads(collected)
        json_path = output_dir / f"{stem}.json"
        json_path.write_text(
            json.dumps(to_whisperx_payload(segments), indent=2, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        return TranscriptionProviderResult(
            success=True,
            json_path=json_path,
            output_dir=output_dir,
            returncode=last_code,
            stdout_tail=tail_lines("\n".join(stdout_acc), max_lines=_TAIL_LINES),
            stderr_tail=tail_lines("\n".join(stderr_acc), max_lines=_TAIL_LINES),
            duration_seconds=time.time() - started,
        )
