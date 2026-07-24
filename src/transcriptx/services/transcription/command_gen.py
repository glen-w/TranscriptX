"""
Copyable transcription command generation (no execution).

Used by the Transcribe Audio page to hand off shell commands for host-side
whispermlx / whispermlx-missing / WhisperX Docker workflows.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class TranscriptionTool(str, Enum):
    WHISPERMLX_SINGLE = "whispermlx_single"
    WHISPERMLX_MISSING = "whispermlx_missing"
    WHISPERX_DOCKER = "whisperx_docker"


@dataclass(frozen=True)
class CommandGenParams:
    """Parameters for a copyable transcription command."""

    tool: TranscriptionTool
    input_path: str
    output_dir: str
    model: str = "large-v3"
    language: str = "en"
    diarize: bool = True
    env_file: str = "whisperx.env"
    whispermlx_binary: str = "whispermlx"
    audio_glob: str = "*.mp3"
    force: bool = False  # overwrite / re-run when JSON exists
    dry_run: bool = False
    fuzzy_json_match: bool = False
    # WhisperX Docker / Linux recipe
    device: str = "cpu"
    compute_type: str = "float16"
    batch_size: int = 16
    min_speakers: int | None = None
    max_speakers: int | None = None
    docker_image: str = "ghcr.io/m-bain/whisperx:latest"
    # Import expects WhisperX / whispermlx JSON (not a selectable alternate format for 1.0)
    expected_output_format: str = "whisperx_json"


@dataclass(frozen=True)
class GeneratedCommand:
    """A shell snippet plus short operator notes (never executed by Streamlit)."""

    title: str
    shell: str
    notes: tuple[str, ...]
    next_step: str = (
        "When WhisperX/whispermlx JSON is ready, open Import Transcript and upload "
        "the output (optionally attach the source recording)."
    )


def _q(value: str) -> str:
    """Shell-quote a path or token (handles spaces)."""
    return shlex.quote(value)


def build_whispermlx_single(params: CommandGenParams) -> GeneratedCommand:
    binary = params.whispermlx_binary.strip() or "whispermlx"
    parts: list[str] = [
        _q(binary),
        _q(params.input_path),
        "--output_dir",
        _q(params.output_dir),
        "--language",
        _q(params.language),
        "--model",
        _q(params.model),
    ]
    if params.diarize:
        parts.append("--diarize")

    env_block = f"""set -a
source {_q(params.env_file)}
set +a

mkdir -p {_q(params.output_dir)}
{" ".join(parts)}
"""
    notes = (
        "Run on the macOS host (Apple MLX). Do not run whispermlx inside the Linux analysis container.",
        "Set HF_TOKEN in whisperx.env when diarization is enabled.",
        "If whispermlx is not on PATH, set WHISPERMLX in whisperx.env or change the binary field.",
        "Expected output: WhisperX/whispermlx JSON for Import Transcript.",
    )
    return GeneratedCommand(
        title="whispermlx (single file or path)",
        shell=env_block.strip() + "\n",
        notes=notes,
    )


def build_whispermlx_batch_loop(params: CommandGenParams) -> GeneratedCommand:
    """Folder batch via a quoted shell loop (spaces-safe)."""
    binary = params.whispermlx_binary.strip() or "whispermlx"
    pattern = params.audio_glob.strip() or "*.mp3"
    diarize_flag = " \\\n        --diarize" if params.diarize else ""
    # Prefer WHISPERMLX from env; fall back to PATH lookup or explicit binary path.
    if binary == "whispermlx":
        binary_default = '$(command -v whispermlx)'
    else:
        binary_default = _q(binary)
    shell = f"""set -a
source {_q(params.env_file)}
set +a

WHISPERMLX="${{WHISPERMLX:-{binary_default}}}"
AUDIO_DIR={_q(params.input_path)}
OUTDIR={_q(params.output_dir)}

mkdir -p "$OUTDIR"

# Quoting protects paths with spaces.
for f in "$AUDIO_DIR"/{pattern}; do
    [ -e "$f" ] || continue
    echo "Processing: $(basename "$f")"
    "$WHISPERMLX" "$f" \\
        --output_dir "$OUTDIR" \\
        --language {_q(params.language)} \\
        --model {_q(params.model)}{diarize_flag}
done
"""
    notes = (
        "Host macOS only. Prefer whispermlx-missing when some files already have JSON.",
        "Glob is unquoted after AUDIO_DIR so the shell expands matches; directory path is quoted.",
        "Resume: re-run skips nothing — use whispermlx-missing for skip-existing behaviour.",
        "Expected output: WhisperX/whispermlx JSON for Import Transcript.",
    )
    return GeneratedCommand(
        title="whispermlx (folder loop)",
        shell=shell.strip() + "\n",
        notes=notes,
    )


def build_whispermlx_missing(params: CommandGenParams) -> GeneratedCommand:
    parts: list[str] = [
        "whispermlx-missing",
        "--source",
        _q(params.input_path),
        "--transcripts",
        _q(params.output_dir),
        "--env-file",
        _q(params.env_file),
    ]
    if params.dry_run:
        parts.append("--dry-run")
    if params.force:
        parts.append("--force")
    if params.fuzzy_json_match:
        parts.append("--fuzzy-json-match")
    # Pass model/language/diarize through to whispermlx
    whisper_args: list[str] = [
        "--language",
        params.language,
        "--model",
        params.model,
    ]
    if params.diarize:
        whisper_args.append("--diarize")
    parts.append("--whisper-args")
    parts.extend(whisper_args)

    shell = " ".join(parts) + "\n"
    notes = (
        "Install once: install -m 755 scripts/whispermlx-missing.py ~/.local/bin/whispermlx-missing",
        "Skips stems that already have matching JSON (resume-friendly). Use --force to re-run.",
        "Preview safely with --dry-run (no HF_TOKEN / binary required for preview).",
        "Paths with spaces are shell-quoted. Run on the macOS host, not inside transcriptx-web.",
        "Live runs stream whispermlx logs; --quiet captures output and shows stderr tails on failure.",
        "Expected output: WhisperX/whispermlx JSON for Import Transcript.",
    )
    return GeneratedCommand(
        title="whispermlx-missing (skip existing JSON)",
        shell=shell,
        notes=notes,
    )


def build_whisperx_docker(params: CommandGenParams) -> GeneratedCommand:
    """Reference docker run for non-macOS / WhisperX recipe (copyable only)."""
    audio_mount = params.input_path.rstrip("/")
    out_mount = params.output_dir.rstrip("/")
    diarize = " --diarize" if params.diarize else ""
    speaker_flags = ""
    if params.min_speakers is not None:
        speaker_flags += f" \\\n    --min_speakers {int(params.min_speakers)}"
    if params.max_speakers is not None:
        speaker_flags += f" \\\n    --max_speakers {int(params.max_speakers)}"
    shell = f"""# WhisperX Docker (Linux/GPU hosts). See docs/recipes/whisperx/.
# Mount audio + output; HF_TOKEN required when diarization is on.
# Expected output format: WhisperX JSON (Import Transcript).

mkdir -p {_q(out_mount)}

docker run --rm \\
  -v {_q(audio_mount)}:/audio \\
  -v {_q(out_mount)}:/output \\
  -e HF_TOKEN \\
  {_q(params.docker_image)} \\
  whisperx /audio \\
    --output_dir /output \\
    --model {_q(params.model)} \\
    --language {_q(params.language)} \\
    --device {_q(params.device)} \\
    --compute_type {_q(params.compute_type)} \\
    --batch_size {int(params.batch_size)}{diarize}{speaker_flags}
"""
    notes = (
        "External recipe only — TranscriptX does not orchestrate WhisperX from Streamlit.",
        "Adjust mounts if input is a single file (mount parent directory).",
        "Import the resulting WhisperX JSON via Import Transcript.",
        "Progress/logs come from the docker/whisperx process on the host terminal.",
    )
    return GeneratedCommand(
        title="WhisperX Docker (external recipe)",
        shell=shell.strip() + "\n",
        notes=notes,
    )


def generate_transcription_command(params: CommandGenParams) -> GeneratedCommand:
    """Build a copyable command for the selected tool."""
    if params.tool is TranscriptionTool.WHISPERMLX_SINGLE:
        # Directory-looking inputs get a batch loop; files get single invocation.
        if params.input_path.rstrip("/").endswith(
            (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".mp4", ".webm")
        ):
            return build_whispermlx_single(params)
        return build_whispermlx_batch_loop(params)
    if params.tool is TranscriptionTool.WHISPERMLX_MISSING:
        return build_whispermlx_missing(params)
    if params.tool is TranscriptionTool.WHISPERX_DOCKER:
        return build_whisperx_docker(params)
    raise ValueError(f"Unknown transcription tool: {params.tool!r}")


def generate_preview_lines(params: CommandGenParams) -> Sequence[str]:
    """Short human-readable summary of the planned handoff."""
    cmd = generate_transcription_command(params)
    return (
        f"Tool: {cmd.title}",
        f"Input: {params.input_path}",
        f"Output: {params.output_dir}",
        f"Model / language: {params.model} / {params.language}",
        f"Diarize: {'yes' if params.diarize else 'no'}",
        f"Dry-run flag: {'yes' if params.dry_run else 'no'}",
        f"Force / overwrite: {'yes' if params.force else 'no'}",
        f"Expected output format: {params.expected_output_format} (Import Transcript)",
    )
