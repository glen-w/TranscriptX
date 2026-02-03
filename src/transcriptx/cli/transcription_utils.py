import os
import subprocess
from rich.console import Console
from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR


def run_whisperx_docker(audio_file_path, config=None):
    """
    Run WhisperX transcription in a Docker container using config options.
    """
    output_dir = DIARISED_TRANSCRIPTS_DIR
    audio_file_name = os.path.basename(str(audio_file_path))
    # Use config or smart defaults
    model = (
        getattr(config.transcription, "model_name", "large-v2")
        if config
        else "large-v2"
    )
    language = getattr(config.transcription, "language", "auto") if config else "auto"
    compute_type = (
        getattr(config.transcription, "compute_type", "float32")
        if config
        else "float32"
    )
    diarize = getattr(config.transcription, "diarize", True) if config else True
    model_download_policy = (
        getattr(config.transcription, "model_download_policy", "anonymous")
        if config
        else "anonymous"
    )
    hf_token = (
        getattr(config.transcription, "huggingface_token", "")
        if config
        else ""
    )
    if not hf_token:
        hf_token = (
            os.getenv("TRANSCRIPTX_HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN") or ""
        )
    min_speakers = getattr(config.transcription, "min_speakers", 1) if config else 1
    max_speakers = getattr(config.transcription, "max_speakers", None) if config else None
    try:
        min_speakers = int(min_speakers)
    except (TypeError, ValueError):
        min_speakers = 1
    if max_speakers is not None:
        try:
            max_speakers = int(max_speakers)
        except (TypeError, ValueError):
            max_speakers = None
    if min_speakers < 1:
        min_speakers = 1
    if max_speakers is not None and max_speakers < min_speakers:
        max_speakers = min_speakers
    device = "cpu"  # For now, always CPU
    whisperx_cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{output_dir}:/data",
        "ghcr.io/jim60105/whisperx:no_model",
        f"/data/{audio_file_name}",
        "--output_dir",
        "/data",
        "--output_format",
        "json",
        "--model",
        model,
    ]
    # Only add --language flag if not "auto" (WhisperX auto-detects when flag is omitted)
    if language and str(language).lower() not in ("auto", "none", ""):
        whisperx_cmd.extend(["--language", language])
    whisperx_cmd.extend(
        [
            "--compute_type",
            compute_type,
            "--device",
            device,
        ]
    )
    if model_download_policy == "require_token" and not hf_token:
        console = Console()
        console.print(
            "[red]Hugging Face token required to download models.[/red]"
        )
        console.print(
            "[dim]Set TRANSCRIPTX_HUGGINGFACE_TOKEN or HF_TOKEN "
            "(or transcription.huggingface_token), or switch "
            "transcription.model_download_policy to 'anonymous'.[/dim]"
        )
        return None
    if diarize and not hf_token:
        console = Console()
        console.print(
            "[yellow]⚠️  No Hugging Face token set; running without diarization.[/yellow]"
        )
        console.print(
            "[dim]To enable diarization, set TRANSCRIPTX_HUGGINGFACE_TOKEN or HF_TOKEN "
            "(or transcription.huggingface_token), or disable diarization in settings.[/dim]"
        )
        diarize = False
    if hf_token:
        whisperx_cmd.extend(["--hf_token", hf_token])
    if diarize:
        whisperx_cmd.append("--diarize")
        whisperx_cmd.extend(["--min_speakers", str(min_speakers)])
        if max_speakers is not None:
            whisperx_cmd.extend(["--max_speakers", str(max_speakers)])
    try:
        result = subprocess.run(
            whisperx_cmd, capture_output=True, text=True, check=True
        )
        console = Console()
        console.print(result.stdout)
        transcript_path = os.path.join(
            output_dir, os.path.splitext(audio_file_name)[0] + ".json"
        )
        return transcript_path if os.path.exists(transcript_path) else None
    except subprocess.CalledProcessError as e:
        console = Console()
        stderr_output = (
            e.stderr if e.stderr is not None else "No error details available"
        )
        console.print(
            f"[red]WhisperX Docker transcription failed:[/red] {stderr_output}"
        )
        return None
