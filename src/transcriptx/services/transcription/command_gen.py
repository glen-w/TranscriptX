"""
Copyable transcription command generation (no execution).

Used by the Transcribe Audio page to hand off shell commands for host-side
whispermlx / whispermlx-missing / WhisperX Docker / Whisper-WebUI workflows.
"""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Sequence

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.services.transcription.granite_mlx_provider import (
    build_gen_kwargs,
    is_turbo_ctc,
    resolve_granite_model,
)
from transcriptx.services.transcription.nemotron_vllm_client import (
    DEFAULT_BASE_URL as _NEMOTRON_BASE_URL,
    DEFAULT_MODEL as _NEMOTRON_MODEL_DEFAULT,
)


class TranscriptionTool(str, Enum):
    WHISPERMLX_SINGLE = "whispermlx_single"
    WHISPERMLX_MISSING = "whispermlx_missing"
    WHISPERX_DOCKER = "whisperx_docker"
    WHISPER_WEBUI_DOCKER = "whisper_webui_docker"
    NEMO_PARAKEET_DOCKER = "nemo_parakeet_docker"
    NEMO_CANARY_DOCKER = "nemo_canary_docker"
    NEMO_NEMOTRON_VLLM = "nemo_nemotron_vllm"
    GRANITE_MLX = "granite_mlx"


# Common Whisper / whispermlx / WhisperX model ids for the command generator.
# Engines may accept additional names; the UI selectbox allows custom entry.
DEFAULT_TRANSCRIPTION_MODEL = "large-v3"
TRANSCRIPTION_MODEL_OPTIONS: tuple[str, ...] = (
    "tiny",
    "tiny.en",
    "base",
    "base.en",
    "small",
    "small.en",
    "medium",
    "medium.en",
    "large-v2",
    "large-v3",
    "large-v3-turbo",
)

# Relative defaults for host terminals when Streamlit runs from a Docker install
# (PATHS.project_root resolves under /opt/venv/.../site-packages, not the git clone).
_HOST_ENV_FILE_RELATIVE = "whisperx.env"
_HOST_SCRIPT_RELATIVE = "scripts/whispermlx-missing.py"
_AUDIO_FILE_SUFFIXES = (
    ".mp3",
    ".wav",
    ".m4a",
    ".flac",
    ".ogg",
    ".mp4",
    ".webm",
)
_POSIX_PASTE_NOTE = (
    "Paste into a POSIX shell (macOS, Linux, Git Bash, or WSL). "
    "This snippet is not PowerShell or cmd.exe."
)
_POWERSHELL_PASTE_NOTE = (
    "Paste into Windows PowerShell 5+ or PowerShell 7. "
    "This snippet is not cmd.exe or a POSIX shell."
)
_WINDOWS_MOUNT_NOTE = (
    "Host paths are quoted as given; TranscriptX does not rewrite "
    "Windows C:\\… mounts into Git Bash or Docker Desktop spelling."
)


def looks_like_audio_file(path: str) -> bool:
    """True when path looks like a single audio/video file (case-insensitive)."""
    stripped = path.rstrip("/\\")
    return Path(stripped).suffix.lower() in _AUDIO_FILE_SUFFIXES


def _strip_trailing_separators(path: str) -> str:
    return path.rstrip("/\\")


def looks_like_container_install_path(path: str | Path) -> bool:
    """True for Docker/venv install paths that are not usable on the Mac host."""
    text = str(path).replace("\\", "/")
    return text == "/opt/venv" or text.startswith("/opt/venv/")


def is_host_repo_root(root: Path) -> bool:
    """True when root looks like the TranscriptX git clone (not a site-packages parent)."""
    return (root / "pyproject.toml").is_file() or (
        root / "scripts" / "whispermlx-missing.py"
    ).is_file()


def default_host_env_file(project_root: Path) -> str:
    """Host path for --env-file / source whisperx.env in generated commands."""
    if looks_like_container_install_path(project_root):
        return _HOST_ENV_FILE_RELATIVE
    if is_host_repo_root(project_root):
        return str(project_root / _HOST_ENV_FILE_RELATIVE)
    return _HOST_ENV_FILE_RELATIVE


def default_host_script_ref(project_root: Path) -> str:
    """Host path/ref for scripts/whispermlx-missing.py in page copy."""
    if looks_like_container_install_path(project_root):
        return _HOST_SCRIPT_RELATIVE
    if is_host_repo_root(project_root):
        return str(project_root / _HOST_SCRIPT_RELATIVE)
    return _HOST_SCRIPT_RELATIVE


@dataclass(frozen=True)
class CommandGenParams:
    """Parameters for a copyable transcription command."""

    tool: TranscriptionTool
    input_path: str
    output_dir: str
    model: str = DEFAULT_TRANSCRIPTION_MODEL
    language: str = "en"
    diarize: bool = True
    env_file: str = "whisperx.env"
    whispermlx_binary: str = "whispermlx"
    audio_glob: str = "*.mp3"
    force: bool = False  # overwrite / re-run when JSON exists
    dry_run: bool = False
    fuzzy_json_match: bool = False
    skip_serial: bool = False
    # WhisperX Docker / Linux recipe
    device: str = "cpu"
    compute_type: str = "float16"
    batch_size: int = 16
    min_speakers: int | None = None
    max_speakers: int | None = None
    docker_image: str = "ghcr.io/m-bain/whisperx:latest"
    # Whisper-WebUI (jhj0517) Gradio deployment
    webui_port: int = 7860
    webui_clone_dir: str = "$HOME/Whisper-WebUI"
    # Import format hint for operator notes / preview
    expected_output_format: str = "whisperx_json"
    keyword_bias_enabled: bool = False
    keyword_list_name: str | None = None
    keywords: tuple[str, ...] = ()
    base_url: str = ""


@dataclass(frozen=True)
class GeneratedCommand:
    """A shell snippet plus short operator notes (never executed by Streamlit)."""

    title: str
    shell: str
    notes: tuple[str, ...]
    next_step: str = (
        "When WhisperX/whispermlx JSON is ready, open Import Transcript and upload "
        "the output (optionally attach the source recording; same-stem audio in the "
        "mounted recordings folder will be linked)."
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
        "Set HF_TOKEN in the host repo whisperx.env when diarization is enabled.",
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
        binary_default = "$(command -v whispermlx)"
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
    if params.skip_serial:
        parts.append("--skip-serial")
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
        "Requires ~/.local/bin on PATH (or run: python3 scripts/whispermlx-missing.py …).",
        "Skips stems that already have matching JSON (resume-friendly). Use --force to re-run.",
        "Use --skip-serial to leave Auto-merge serial parts / voice-note runs untranscribed.",
        "Preview safely with --dry-run (no HF_TOKEN / binary required for preview).",
        "Paths with spaces are shell-quoted. Run on the macOS host, not inside transcriptx-web.",
        "--env-file must be the host repo whisperx.env (not a container path under /opt/venv).",
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
    audio_mount = _strip_trailing_separators(params.input_path)
    out_mount = _strip_trailing_separators(params.output_dir)
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
        "Copyable recipe — or use Transcribe Audio → Run in app when Docker is visible.",
        "Adjust mounts if input is a single file (mount parent directory).",
        "Import the resulting WhisperX JSON via Import Transcript.",
        "Progress/logs come from the docker/whisperx process on the host terminal.",
    )
    return GeneratedCommand(
        title="WhisperX Docker (external recipe)",
        shell=shell.strip() + "\n",
        notes=notes,
    )


_DEFAULT_NEMO_IMAGE = "nvcr.io/nvidia/nemo:24.07.1"
_PARAKEET_MODEL_DEFAULT = "nvidia/parakeet-tdt-0.6b-v3"
_CANARY_MODEL_DEFAULT = "nvidia/canary-1b"


def build_nemo_parakeet_docker(params: CommandGenParams) -> GeneratedCommand:
    return _build_nemo_asr_docker(
        params,
        title="NeMo Parakeet Docker (Theme K)",
        model_hint=_PARAKEET_MODEL_DEFAULT,
    )


def build_nemo_canary_docker(params: CommandGenParams) -> GeneratedCommand:
    return _build_nemo_asr_docker(
        params,
        title="NeMo Canary Docker (Theme K)",
        model_hint=_CANARY_MODEL_DEFAULT,
    )


def _nemotron_keyword_flags(params: CommandGenParams) -> str:
    if not params.keyword_bias_enabled:
        return ""
    flags = []
    for term in params.keywords:
        stripped = str(term).strip()
        if stripped:
            flags.append(f"--keyword {_q(stripped)}")
    if not flags:
        return ""
    return " \\\n  " + " \\\n  ".join(flags)


def build_nemo_nemotron_vllm(params: CommandGenParams) -> GeneratedCommand:
    audio_mount = _strip_trailing_separators(params.input_path)
    out_mount = _strip_trailing_separators(params.output_dir)
    model = params.model.strip() or _NEMOTRON_MODEL_DEFAULT
    base_url = params.base_url.strip() or _NEMOTRON_BASE_URL
    diarize_flag = "" if params.diarize else " \\\n  --no-diarize"
    keyword_flags = _nemotron_keyword_flags(params)
    stem_expr = '$(basename "' + audio_mount.replace('"', "") + '")'
    if looks_like_audio_file(audio_mount):
        client_block = f"""python3 -m transcriptx.services.transcription.nemotron_vllm_client \\
  --audio {_q(audio_mount)} \\
  --output-raw {_q(out_mount)}/{stem_expr}.nemotron.json \\
  --base-url {_q(base_url)} \\
  --model {_q(model)}{diarize_flag}{keyword_flags}

python3 -m transcriptx.services.transcription.nemotron_json_to_whisperx \\
  --input {_q(out_mount)}/{stem_expr}.nemotron.json \\
  --output {_q(out_mount)}/{stem_expr}.json
"""
    else:
        client_block = f"""for f in {_q(audio_mount)}/*.{'{mp3,wav,m4a,flac,ogg}'}; do
  [ -e "$f" ] || continue
  stem=$(basename "$f")
  python3 -m transcriptx.services.transcription.nemotron_vllm_client \\
    --audio "$f" \\
    --output-raw {_q(out_mount)}/"$stem".nemotron.json \\
    --base-url {_q(base_url)} \\
    --model {_q(model)}{diarize_flag}{keyword_flags}
  python3 -m transcriptx.services.transcription.nemotron_json_to_whisperx \\
    --input {_q(out_mount)}/"$stem".nemotron.json \\
    --output {_q(out_mount)}/"${{stem%.*}}".json
done
"""
    shell = f"""# Nemotron 3.5 Transcribe — CUDA Linux / WSL2 (not macOS Run-in-app).
# On macOS prefer whispermlx or Granite Speech. BF16 wants ~1× H100 80 GB;
# use the FP8/NVFP4 Hub ids on Blackwell. Serve stays operator-owned.
# Full flags: docs/recipes/nemotron-transcribe/README.md

mkdir -p {_q(out_mount)}

# Optional — start the local server ONCE (TranscriptX does not daemonize it):
# export VLLM_PLUGINS=nemo_speechlm
# export VLLM_MAX_AUDIO_DECODE_DURATION_S=3600
# vllm serve {_q(model)} \\
#   --host 127.0.0.1 --port 8000 --trust-remote-code --dtype bfloat16 \\
#   --gpu-memory-utilization 0.94 --max-model-len 65536 \\
#   --middleware nemo.collections.speechlm2.vllm.salm.ctc_serving.ctc_timestamp_middleware

{client_block}"""
    notes = (
        "Theme K — paste on a CUDA host with a local vLLM/NIM at 127.0.0.1.",
        "Full recipe: docs/recipes/nemotron-transcribe/README.md",
        "OpenMDW-1.1 weights; user-triggered download on first serve.",
        "Default endpoint is loopback only (no silent cloud NIM).",
        "Expected output: WhisperX-shaped JSON for Import Transcript.",
    )
    return GeneratedCommand(
        title="Nemotron 3.5 Transcribe (local vLLM)",
        shell=shell.strip() + "\n",
        notes=notes,
    )


def _build_nemo_asr_docker(
    params: CommandGenParams, *, title: str, model_hint: str
) -> GeneratedCommand:
    audio_mount = _strip_trailing_separators(params.input_path)
    out_mount = _strip_trailing_separators(params.output_dir)
    image = params.docker_image.strip() or _DEFAULT_NEMO_IMAGE
    model = params.model.strip() or model_hint
    shell = f"""# {title} — Linux CUDA host (not macOS Run-in-app).
# On macOS prefer whispermlx; use this Copy command on a CUDA machine only.
# 1) Run NeMo transcription into JSONL (customize inner command per recipe).
# 2) Convert to WhisperX-shaped JSON for Import Transcript.

mkdir -p {_q(out_mount)}

docker run --rm --gpus all \\
  -v {_q(audio_mount)}:/audio:ro \\
  -v {_q(out_mount)}:/output \\
  {_q(image)} \\
  bash -lc 'echo "Replace with NeMo transcribe for model {model}; see docs/recipes/parakeet/" && exit 1'

# After NeMo writes hypotheses.jsonl under the output mount:
python3 -m transcriptx.services.transcription.nemo_json_to_whisperx \\
  --input {_q(out_mount)}/hypotheses.jsonl \\
  --output {_q(out_mount)}/$(basename "{audio_mount}").json
"""
    notes = (
        "Theme K only — not Run-in-app until Wave 4 provider is configured on host.",
        "Full recipe: docs/recipes/parakeet/README.md",
        "CC-BY-4.0 NeMo weights; user-triggered download on first run.",
        "Expected output: WhisperX-shaped JSON for Import Transcript.",
    )
    return GeneratedCommand(
        title=title,
        shell=shell.strip() + "\n",
        notes=notes,
    )


def build_whisper_webui_docker(params: CommandGenParams) -> GeneratedCommand:
    """Deploy jhj0517/Whisper-WebUI (Gradio) via Docker — copyable only."""
    out_mount = _strip_trailing_separators(params.output_dir) or "./outputs"
    image = params.docker_image.strip() or "jhj0517/whisper-webui:v1.0.8-4def223"
    port = int(params.webui_port) if params.webui_port else 7860
    clone_dir = params.webui_clone_dir.strip() or "$HOME/Whisper-WebUI"
    gpu_flag = " \\\n  --gpus all" if params.device == "cuda" else ""
    diarize_hint = "on" if params.diarize else "off"
    shell = f"""# Whisper-WebUI (jhj0517) — optional third-party Gradio recipe.
# TranscriptX does not distribute, embed, fork, or guarantee this service.
# See docs/recipes/whisper-webui/README.md (ownership disclaimer).
# Apple Silicon: container is CPU inference — prefer whispermlx for Metal/MLX speed.
# Expected output: SRT / WebVTT → Import Transcript. Port binds to 127.0.0.1 only.

CLONE_DIR={_q(clone_dir) if not clone_dir.startswith("$") else clone_dir}
OUTDIR={_q(out_mount)}
PORT={port}

if [ ! -d "$CLONE_DIR/.git" ]; then
  git clone --depth 1 https://github.com/jhj0517/Whisper-WebUI.git "$CLONE_DIR"
fi
mkdir -p "$OUTDIR" "$CLONE_DIR/outputs" "$CLONE_DIR/models" "$CLONE_DIR/configs"

# Prefer the pinned Hub tag. Compose alternative: docs/recipes/whisper-webui/
docker run --rm -d \\
  --name whisper-webui \\
  -p "127.0.0.1:$PORT:7860"{gpu_flag} \\
  -v "$CLONE_DIR/models:/Whisper-WebUI/models" \\
  -v "$OUTDIR:/Whisper-WebUI/outputs" \\
  -v "$CLONE_DIR/configs:/Whisper-WebUI/configs" \\
  -e HF_TOKEN \\
  {_q(image)}

echo "Open http://127.0.0.1:$PORT"
echo "In the Gradio UI set model={_q(params.model)} language={_q(params.language)} diarization={diarize_hint}"
echo "Download SRT/VTT from outputs, then Import Transcript in TranscriptX."
echo "Stop: docker stop whisper-webui"
"""
    notes = (
        "Optional interoperability recipe — TranscriptX does not own or guarantee Whisper-WebUI.",
        "Apple Silicon: expect CPU inference in Docker; native MLX (whispermlx) is usually faster.",
        "Port binds to 127.0.0.1 only (not 0.0.0.0). Open http://127.0.0.1:<port>.",
        "Upload audio in Gradio; exports land in the mounted outputs folder (SRT/VTT preferred).",
        "Models cache under the clone's models/ directory (multi-GB). TranscriptX does not prune it.",
        "Diarization: you supply HF_TOKEN and accept pyannote terms; quality ≠ WhisperX JSON path.",
        "Upstream updates may break this recipe; pin the documented image tag.",
        "Removal: docker stop whisper-webui; optional rm of clone/outputs/image — see recipe README.",
    )
    return GeneratedCommand(
        title="Whisper-WebUI Docker (Gradio)",
        shell=shell.strip() + "\n",
        notes=notes,
        next_step=(
            "When SRT/VTT (or other supported export) is ready in the outputs folder, "
            "open Import Transcript and upload it (optionally attach the source recording; "
            "same-stem audio in the mounted recordings folder will be linked)."
        ),
    )


def _granite_options(params: CommandGenParams) -> TranscriptionOptions:
    return TranscriptionOptions(
        provider_id="granite_mlx",
        model=params.model or "",
        language=params.language or "en",
        diarize=params.diarize,
        keyword_bias_enabled=params.keyword_bias_enabled,
        keywords=tuple(params.keywords or ()),
    )


def _granite_copy_model(params: CommandGenParams) -> str:
    return resolve_granite_model(_granite_options(params))


def _granite_gen_kwargs(params: CommandGenParams) -> dict:
    options = _granite_options(params)
    return build_gen_kwargs(options, model_id=resolve_granite_model(options))


def _granite_generate_cli_lines(params: CommandGenParams) -> tuple[str, str]:
    """Return (model_id, extra generate flags after --format json)."""
    model = _granite_copy_model(params)
    kwargs = _granite_gen_kwargs(params)
    extra = ""
    if kwargs:
        extra = f" \\\n  --gen-kwargs {_q(json.dumps(kwargs, ensure_ascii=False))}"
    return model, extra


def build_granite_mlx(params: CommandGenParams) -> GeneratedCommand:
    """Copyable mlx-audio Granite Speech command (Apple Silicon host)."""
    model, extra_flags = _granite_generate_cli_lines(params)
    audio = _strip_trailing_separators(params.input_path)
    out_mount = _strip_trailing_separators(params.output_dir)
    turbo = is_turbo_ctc(model)
    shell = f"""# Granite Speech via mlx-audio (Apple Silicon host — not the analysis venv).
# pip install -U mlx-audio jinja2
# Point MLX_AUDIO_PYTHON at that interpreter. First run downloads Hub weights.

MLX_AUDIO_PYTHON="${{MLX_AUDIO_PYTHON:-python3}}"
OUTDIR={_q(out_mount)}
mkdir -p "$OUTDIR"

"$MLX_AUDIO_PYTHON" -m mlx_audio.stt.generate \\
  --model {_q(model)} \\
  --audio {_q(audio)} \\
  --output-path "$OUTDIR/granite_raw" \\
  --format json{extra_flags}

python3 -m transcriptx.services.transcription.granite_json_to_whisperx \\
  --input "$OUTDIR/granite_raw.json" \\
  --output "$OUTDIR/$(basename {_q(audio)} | sed 's/\\.[^.]*$//').json"
"""
    notes = (
        "Run on the macOS host (Apple MLX). Do not install mlx-audio in the analysis venv.",
        "Set MLX_AUDIO_PYTHON to the interpreter that has mlx-audio>=0.5.9 and jinja2.",
        (
            "TurboCTC is undiarized speed ASR; no keyword biasing or speaker attribution. "
            "Use 4.1-2b-plus for meetings."
            if turbo
            else "Diarize uses granite-speech-4.1-2b-plus (task=saa). No HF_TOKEN / pyannote."
        ),
        "Keyword biasing is off unless you enabled it on 5.0-2b; cap is 2000 terms.",
        "Long files: IBM recommends ~2 min chunks for 5.0-2b; Run in app chunks automatically.",
        "Speaker-attributed mode does not emit WhisperX-grade word timestamps.",
        "Expected output: WhisperX-shaped JSON for Import Transcript.",
    )
    return GeneratedCommand(
        title="Granite Speech (mlx-audio)",
        shell=shell.strip() + "\n",
        notes=notes,
    )


def generate_transcription_command(params: CommandGenParams) -> GeneratedCommand:
    """Build a copyable command for the selected tool."""
    if params.tool is TranscriptionTool.WHISPERMLX_SINGLE:
        if looks_like_audio_file(params.input_path):
            generated = build_whispermlx_single(params)
        else:
            generated = build_whispermlx_batch_loop(params)
    elif params.tool is TranscriptionTool.WHISPERMLX_MISSING:
        generated = build_whispermlx_missing(params)
    elif params.tool is TranscriptionTool.WHISPERX_DOCKER:
        generated = build_whisperx_docker(params)
    elif params.tool is TranscriptionTool.WHISPER_WEBUI_DOCKER:
        generated = build_whisper_webui_docker(params)
    elif params.tool is TranscriptionTool.NEMO_PARAKEET_DOCKER:
        generated = build_nemo_parakeet_docker(params)
    elif params.tool is TranscriptionTool.NEMO_CANARY_DOCKER:
        generated = build_nemo_canary_docker(params)
    elif params.tool is TranscriptionTool.NEMO_NEMOTRON_VLLM:
        generated = build_nemo_nemotron_vllm(params)
    elif params.tool is TranscriptionTool.GRANITE_MLX:
        generated = build_granite_mlx(params)
    else:
        raise ValueError(f"Unknown transcription tool: {params.tool!r}")
    extra_notes = (_POSIX_PASTE_NOTE,)
    if params.tool in (
        TranscriptionTool.WHISPERX_DOCKER,
        TranscriptionTool.NEMO_PARAKEET_DOCKER,
        TranscriptionTool.NEMO_CANARY_DOCKER,
        TranscriptionTool.NEMO_NEMOTRON_VLLM,
    ):
        extra_notes = extra_notes + (_WINDOWS_MOUNT_NOTE,)
    return GeneratedCommand(
        title=generated.title,
        shell=generated.shell,
        notes=generated.notes + extra_notes,
        next_step=generated.next_step,
    )


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
        f"Skip likely serial: {'yes' if params.skip_serial else 'no'}",
        f"Expected output format: {params.expected_output_format} (Import Transcript)",
    )


def _ps_q(value: str) -> str:
    """PowerShell single-quote a path or token."""
    return "'" + str(value).replace("'", "''") + "'"


def _ps_join(parts: Sequence[str]) -> str:
    return " ".join(parts)


def generate_transcription_command_powershell(
    params: CommandGenParams,
) -> GeneratedCommand:
    """Build a copyable PowerShell snippet for the selected tool (Theme K)."""
    if params.tool is TranscriptionTool.WHISPERMLX_SINGLE:
        generated = _build_whispermlx_powershell(params)
    elif params.tool is TranscriptionTool.WHISPERMLX_MISSING:
        generated = _build_whispermlx_missing_powershell(params)
    elif params.tool is TranscriptionTool.WHISPERX_DOCKER:
        generated = _build_whisperx_docker_powershell(params)
    elif params.tool is TranscriptionTool.WHISPER_WEBUI_DOCKER:
        generated = _build_whisper_webui_powershell(params)
    elif params.tool is TranscriptionTool.NEMO_PARAKEET_DOCKER:
        generated = build_nemo_parakeet_docker(params)
    elif params.tool is TranscriptionTool.NEMO_CANARY_DOCKER:
        generated = build_nemo_canary_docker(params)
    elif params.tool is TranscriptionTool.NEMO_NEMOTRON_VLLM:
        generated = _build_nemo_nemotron_vllm_powershell(params)
    elif params.tool is TranscriptionTool.GRANITE_MLX:
        generated = _build_granite_mlx_powershell(params)
    else:
        raise ValueError(f"Unknown transcription tool: {params.tool!r}")
    notes = generated.notes + (_POWERSHELL_PASTE_NOTE,)
    if params.tool in (
        TranscriptionTool.WHISPERX_DOCKER,
        TranscriptionTool.NEMO_PARAKEET_DOCKER,
        TranscriptionTool.NEMO_CANARY_DOCKER,
        TranscriptionTool.NEMO_NEMOTRON_VLLM,
    ):
        notes = notes + (_WINDOWS_MOUNT_NOTE,)
    return GeneratedCommand(
        title=generated.title + " (PowerShell)",
        shell=generated.shell,
        notes=notes,
        next_step=generated.next_step,
    )


def _build_nemo_nemotron_vllm_powershell(params: CommandGenParams) -> GeneratedCommand:
    audio = _strip_trailing_separators(params.input_path)
    out_mount = _strip_trailing_separators(params.output_dir)
    model = params.model.strip() or _NEMOTRON_MODEL_DEFAULT
    base_url = params.base_url.strip() or _NEMOTRON_BASE_URL
    diarize_flag = "" if params.diarize else " --no-diarize"
    keyword_flags = ""
    if params.keyword_bias_enabled:
        parts = [
            f"--keyword {_ps_q(str(term).strip())}"
            for term in params.keywords
            if str(term).strip()
        ]
        if parts:
            keyword_flags = " " + " ".join(parts)
    shell = f"""# Nemotron 3.5 Transcribe — CUDA host / WSL2. Serve stays operator-owned.
# On macOS prefer whispermlx. See docs/recipes/nemotron-transcribe/README.md
$OutDir = {_ps_q(out_mount)}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$Stem = [System.IO.Path]::GetFileName({_ps_q(audio)})
python -m transcriptx.services.transcription.nemotron_vllm_client --audio {_ps_q(audio)} --output-raw (Join-Path $OutDir ($Stem + '.nemotron.json')) --base-url {_ps_q(base_url)} --model {_ps_q(model)}{diarize_flag}{keyword_flags}
python -m transcriptx.services.transcription.nemotron_json_to_whisperx --input (Join-Path $OutDir ($Stem + '.nemotron.json')) --output (Join-Path $OutDir ([System.IO.Path]::GetFileNameWithoutExtension($Stem) + '.json'))
"""
    notes = (
        "Theme K — paste on a CUDA host with local vLLM at 127.0.0.1.",
        "Full recipe: docs/recipes/nemotron-transcribe/README.md",
        "OpenMDW-1.1 weights; user-triggered download on first serve.",
        "Expected output: WhisperX-shaped JSON for Import Transcript.",
    )
    return GeneratedCommand(
        title="Nemotron 3.5 Transcribe (local vLLM)",
        shell=shell.strip() + "\n",
        notes=notes,
    )


def _build_granite_mlx_powershell(params: CommandGenParams) -> GeneratedCommand:
    model = _granite_copy_model(params)
    kwargs = _granite_gen_kwargs(params)
    extra = ""
    if kwargs:
        extra = f" --gen-kwargs {_ps_q(json.dumps(kwargs, ensure_ascii=False))}"
    audio = _strip_trailing_separators(params.input_path)
    out_mount = _strip_trailing_separators(params.output_dir)
    shell = f"""# mlx-audio is Apple Silicon. This snippet is for completeness only.
$Py = if ($env:MLX_AUDIO_PYTHON) {{ $env:MLX_AUDIO_PYTHON }} else {{ "python3" }}
$OutDir = {_ps_q(out_mount)}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
& $Py -m mlx_audio.stt.generate --model {_ps_q(model)} --audio {_ps_q(audio)} --output-path (Join-Path $OutDir 'granite_raw') --format json{extra}
& python -m transcriptx.services.transcription.granite_json_to_whisperx --input (Join-Path $OutDir 'granite_raw.json') --output (Join-Path $OutDir 'meeting.json')
"""
    notes = (
        "mlx-audio is Apple Silicon; prefer POSIX on the Mac host.",
        "Expected output: WhisperX-shaped JSON for Import Transcript.",
    )
    return GeneratedCommand(
        title="Granite Speech (mlx-audio)",
        shell=shell.strip() + "\n",
        notes=notes,
    )


def _build_whispermlx_powershell(params: CommandGenParams) -> GeneratedCommand:
    binary = params.whispermlx_binary.strip() or "whispermlx"
    env = _ps_q(params.env_file)
    out = _ps_q(params.output_dir)
    parts = [
        "&",
        _ps_q(binary),
        _ps_q(params.input_path),
        "--output_dir",
        _ps_q(params.output_dir),
        "--language",
        _ps_q(params.language),
        "--model",
        _ps_q(params.model),
    ]
    if params.diarize:
        parts.append("--diarize")
    shell = f"""if (Test-Path {env}) {{
  Get-Content {env} | ForEach-Object {{
    if ($_ -match '^\\s*#' -or $_ -notmatch '=') {{ return }}
    $k,$v = $_ -split '=',2
    Set-Item -Path ("Env:" + $k.Trim()) -Value $v.Trim().Trim("'").Trim('"')
  }}
}}
New-Item -ItemType Directory -Force -Path {out} | Out-Null
{_ps_join(parts)}
"""
    notes = (
        "whispermlx is a macOS/MLX binary; this PowerShell form is for hosts "
        "that already have it on PATH.",
        "Set HF_TOKEN in whisperx.env when diarization is enabled.",
        "Expected output: WhisperX/whispermlx JSON for Import Transcript.",
    )
    return GeneratedCommand(
        title="whispermlx",
        shell=shell.strip() + "\n",
        notes=notes,
    )


def _build_whispermlx_missing_powershell(params: CommandGenParams) -> GeneratedCommand:
    parts = [
        "python",
        _ps_q("scripts/whispermlx-missing.py"),
        "--source",
        _ps_q(params.input_path),
        "--transcripts",
        _ps_q(params.output_dir),
        "--env-file",
        _ps_q(params.env_file),
    ]
    if params.dry_run:
        parts.append("--dry-run")
    if params.force:
        parts.append("--force")
    if params.fuzzy_json_match:
        parts.append("--fuzzy-json-match")
    if params.skip_serial:
        parts.append("--skip-serial")
    parts.extend(
        ["--whisper-args", "--language", params.language, "--model", params.model]
    )
    if params.diarize:
        parts.append("--diarize")
    notes = (
        "Run from the git clone so scripts/whispermlx-missing.py resolves.",
        "Requires a Python that can run the helper (stdlib-only).",
        "Expected output: WhisperX/whispermlx JSON for Import Transcript.",
    )
    return GeneratedCommand(
        title="whispermlx-missing",
        shell=_ps_join(parts) + "\n",
        notes=notes,
    )


def _build_whisperx_docker_powershell(params: CommandGenParams) -> GeneratedCommand:
    audio_mount = _strip_trailing_separators(params.input_path)
    out_mount = _strip_trailing_separators(params.output_dir)
    gpu = " --gpus all" if params.device == "cuda" else ""
    diarize = " --diarize" if params.diarize else ""
    speaker = ""
    if params.min_speakers is not None:
        speaker += f" --min_speakers {int(params.min_speakers)}"
    if params.max_speakers is not None:
        speaker += f" --max_speakers {int(params.max_speakers)}"
    shell = f"""New-Item -ItemType Directory -Force -Path {_ps_q(out_mount)} | Out-Null
docker run --rm{gpu} `
  -v {_ps_q(audio_mount + ':/audio')} `
  -v {_ps_q(out_mount + ':/output')} `
  -e HF_TOKEN `
  {_ps_q(params.docker_image)} `
  whisperx /audio `
    --output_dir /output `
    --model {_ps_q(params.model)} `
    --language {_ps_q(params.language)} `
    --device {_ps_q(params.device)} `
    --compute_type {_ps_q(params.compute_type)} `
    --batch_size {int(params.batch_size)}{diarize}{speaker}
"""
    notes = (
        "External recipe — run on a host with Docker Desktop or Engine.",
        "Adjust mounts if input is a single file (mount the parent directory).",
        "Import the resulting WhisperX JSON via Import Transcript.",
    )
    return GeneratedCommand(
        title="WhisperX Docker",
        shell=shell.strip() + "\n",
        notes=notes,
    )


def _build_whisper_webui_powershell(params: CommandGenParams) -> GeneratedCommand:
    out_mount = _strip_trailing_separators(params.output_dir) or "./outputs"
    image = params.docker_image.strip() or "jhj0517/whisper-webui:v1.0.8-4def223"
    port = int(params.webui_port) if params.webui_port else 7860
    clone_dir = params.webui_clone_dir.strip() or "$HOME/Whisper-WebUI"
    gpu = " --gpus all" if params.device == "cuda" else ""
    clone_expr = _ps_q(clone_dir) if not clone_dir.startswith("$") else clone_dir
    shell = f"""$CloneDir = {clone_expr}
$OutDir = {_ps_q(out_mount)}
$Port = {port}
if (-not (Test-Path (Join-Path $CloneDir '.git'))) {{
  git clone --depth 1 https://github.com/jhj0517/Whisper-WebUI.git $CloneDir
}}
New-Item -ItemType Directory -Force -Path $OutDir,(Join-Path $CloneDir 'outputs'),(Join-Path $CloneDir 'models'),(Join-Path $CloneDir 'configs') | Out-Null
docker run --rm -d --name whisper-webui -p "127.0.0.1:${{Port}}:7860"{gpu} `
  -v "${{CloneDir}}/models:/Whisper-WebUI/models" `
  -v "${{OutDir}}:/Whisper-WebUI/outputs" `
  -v "${{CloneDir}}/configs:/Whisper-WebUI/configs" `
  -e HF_TOKEN `
  {_ps_q(image)}
Write-Host "Open http://127.0.0.1:$Port"
"""
    notes = (
        "Optional interoperability recipe — TranscriptX does not own Whisper-WebUI.",
        "Port binds to 127.0.0.1 only. Export SRT/VTT then Import Transcript.",
    )
    return GeneratedCommand(
        title="Whisper-WebUI Docker",
        shell=shell.strip() + "\n",
        notes=notes,
        next_step=(
            "When SRT/VTT is ready in the outputs folder, open Import Transcript "
            "and upload it."
        ),
    )
