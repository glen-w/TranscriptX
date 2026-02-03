import os
import shutil
import subprocess
import time
import threading
from pathlib import Path
from datetime import timedelta
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from transcriptx.core.utils.paths import RECORDINGS_DIR, DIARISED_TRANSCRIPTS_DIR

# Import core transcription functions (for internal use)
from transcriptx.core.transcription_runtime import (
    check_whisperx_compose_service as _check_whisperx_compose_service_core,
    start_whisperx_compose_service as _start_whisperx_compose_service_core,
)

# Container name from docker-compose.whisperx.yml
WHISPERX_CONTAINER_NAME = "transcriptx-whisperx"
COMPOSE_FILE = "docker-compose.whisperx.yml"

console = Console()


def estimate_audio_duration(audio_file_path):
    """
    Estimate audio duration in seconds.
    Tries ffprobe first, falls back to file size estimation.

    Returns:
        float: Estimated duration in seconds, or None if unable to estimate
    """
    # Try ffprobe first (most accurate)
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(audio_file_path),
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            duration = float(result.stdout.strip())
            if duration > 0:
                return duration
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass

    # Fallback: rough estimate based on file size
    # MP3 is typically ~1MB per minute at 128kbps
    # This is very rough but better than nothing
    try:
        file_size_mb = audio_file_path.stat().st_size / (1024 * 1024)
        # Conservative estimate: ~1MB per minute for typical MP3
        estimated_minutes = file_size_mb / 1.0
        return estimated_minutes * 60
    except (OSError, AttributeError):
        return None


def run_whisperx_compose(audio_file_path, config=None):
    """
    Run WhisperX transcription using the Docker Compose container.
    This uses docker exec on the running compose container.
    """
    console = Console()

    # Ensure audio_file_path is valid
    if audio_file_path is None:
        console.print("[red]Error: audio_file_path is None[/red]")
        return None

    # Ensure audio_file_path is a Path object
    try:
        audio_file_path = Path(audio_file_path)
    except (TypeError, ValueError) as e:
        console.print(f"[red]Error: Invalid audio file path: {e}[/red]")
        return None

    audio_file_name = audio_file_path.name
    if not audio_file_name:
        console.print(
            "[red]Error: Could not extract filename from audio file path[/red]"
        )
        return None

    # Use config or smart defaults
    if config and hasattr(config, "transcription") and config.transcription:
        # Use config values, but fallback to defaults if None or empty
        model = getattr(config.transcription, "model_name", None) or "large-v2"
        # Handle None/empty language (auto-detect) by defaulting to 'auto'
        language = getattr(config.transcription, "language", None) or "auto"
        compute_type = getattr(config.transcription, "compute_type", None) or "float16"
        diarize = getattr(config.transcription, "diarize", True)
        min_speakers = getattr(config.transcription, "min_speakers", 1)
        max_speakers = getattr(config.transcription, "max_speakers", None)
        model_download_policy = (
            getattr(config.transcription, "model_download_policy", None) or "anonymous"
        )
        hf_token = getattr(config.transcription, "huggingface_token", None) or ""
    else:
        model = "large-v2"
        language = "auto"
        compute_type = "float16"
        diarize = True
        min_speakers = 1
        max_speakers = None
        model_download_policy = "anonymous"
        hf_token = ""

    # Backstop: accept env vars even if config didn't pick them up.
    if not hf_token:
        hf_token = os.getenv("TRANSCRIPTX_HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN") or ""

    # Normalize speaker bounds (defensive; WhisperX expects min <= max when max is set).
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

    # Auto-adjust compute_type for CPU: float16 is not supported on CPU
    if device == "cpu" and compute_type == "float16":
        console.print(
            "[yellow]⚠️  Warning: float16 is not supported on CPU. Switching to float32.[/yellow]"
        )
        compute_type = "float32"

    # Ensure all required parameters are set (validate they're not None or empty)
    # Note: language can be "auto" which is valid
    if not model or not compute_type or not device:
        console.print(
            "[red]Error: Missing required WhisperX configuration parameters[/red]"
        )
        console.print(
            f"[dim]model={model}, language={language}, compute_type={compute_type}, device={device}[/dim]"
        )
        return None

    if model_download_policy == "require_token" and not hf_token:
        console.print(
            "[red]Error: Hugging Face token required to download models.[/red]"
        )
        console.print(
            "[dim]Set TRANSCRIPTX_HUGGINGFACE_TOKEN or HF_TOKEN "
            "(or transcription.huggingface_token), or switch "
            "transcription.model_download_policy to 'anonymous'.[/dim]"
        )
        return None
    if diarize and not hf_token:
        console.print(
            "[yellow]⚠️  No Hugging Face token set; running without diarization.[/yellow]"
        )
        console.print(
            "[dim]To enable diarization, set TRANSCRIPTX_HUGGINGFACE_TOKEN or HF_TOKEN "
            "(or transcription.huggingface_token), or disable diarization in settings.[/dim]"
        )
        diarize = False

    # Ensure the audio file exists
    if not audio_file_path.exists():
        console.print(f"[red]Error: Audio file not found: {audio_file_path}[/red]")
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

    # Ensure the audio file is in the recordings directory (mounted as /data/input)
    if not RECORDINGS_DIR:
        console.print("[red]Error: RECORDINGS_DIR is not set[/red]")
        return None
    recordings_dir = Path(RECORDINGS_DIR)
    recordings_dir.mkdir(parents=True, exist_ok=True)

    # Copy audio file to recordings directory if it's not already there
    target_audio_path = recordings_dir / audio_file_name
    if (
        not target_audio_path.exists()
        or target_audio_path.resolve() != audio_file_path.resolve()
    ):
        console.print(f"[cyan]Copying audio file to recordings directory...[/cyan]")
        try:
            shutil.copy2(audio_file_path, target_audio_path)
        except Exception as e:
            console.print(f"[red]Error copying audio file: {e}[/red]")
            return None

    # Build the whisperx command using docker exec on the running container
    # The container mounts ./data/recordings as /data/input and ./data/transcripts as /data/output
    # The entrypoint is overridden to /bin/bash, so we can call whisperx directly
    whisperx_cmd = [
        "docker",
        "exec",
        WHISPERX_CONTAINER_NAME,
        "whisperx",  # Match working command
        f"/data/input/{audio_file_name}",
        "--output_dir",
        "/data/output",
        "--output_format",
        "json",
        "--model",
        str(model),
    ]
    # Only add --language flag if not "auto" (WhisperX auto-detects when flag is omitted)
    if language and str(language).lower() not in ("auto", "none", ""):
        whisperx_cmd.extend(["--language", str(language)])
    whisperx_cmd.extend(
        [
            "--compute_type",
            str(compute_type),
            "--device",
            str(device),
        ]
    )
    if hf_token:
        whisperx_cmd.extend(["--hf_token", str(hf_token)])
    if diarize:
        whisperx_cmd.append("--diarize")
        whisperx_cmd.extend(["--min_speakers", str(min_speakers)])
        if max_speakers is not None:
            whisperx_cmd.extend(["--max_speakers", str(max_speakers)])

    # Final check - ensure container is ready before executing
    if not _check_whisperx_compose_service_core():
        console.print(
            "[red]Error: WhisperX container is not ready. Please wait and try again.[/red]"
        )
        return None

    try:
        # Estimate audio duration for better time estimate
        audio_duration = estimate_audio_duration(target_audio_path)
        if audio_duration:
            duration_min = audio_duration / 60
            # WhisperX on CPU typically takes 10-30x real-time, sometimes more
            # Conservative estimate: 20x real-time for CPU
            estimated_minutes = max(duration_min * 20, 5)  # At least 5 minutes
            time_estimate = f"Estimated time: {int(estimated_minutes)}-{int(estimated_minutes * 1.5)} minutes"
        else:
            time_estimate = "This may take 30+ minutes for long files"

        console.print(
            f"[cyan]Running WhisperX via Docker Compose container for: {audio_file_name}[/cyan]"
        )
        console.print(
            f"[dim]{time_estimate} (CPU transcription is slower but more accurate)[/dim]"
        )

        # Run with real-time output streaming and progress indicator
        start_time = time.time()
        stdout_lines = []
        stderr_lines = []
        return_code = None

        # Create progress indicator
        # Use a simpler progress display since we can't know exact progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=False,
        ) as progress:
            task = progress.add_task(
                "[cyan]Transcribing audio...", total=None  # Indeterminate progress
            )

            # Start subprocess with streaming output
            process = subprocess.Popen(
                whisperx_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            # Function to read stdout
            def read_stdout():
                try:
                    for line in process.stdout:
                        stdout_lines.append(line)
                except Exception:
                    pass

            # Function to read stderr
            def read_stderr():
                try:
                    for line in process.stderr:
                        stderr_lines.append(line)
                except Exception:
                    pass

            # Start reading threads
            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stdout_thread.start()
            stderr_thread.start()

            # Wait for process to complete, updating progress description periodically
            last_update = 0
            while process.poll() is None:
                elapsed = time.time() - start_time
                # Update description every 5 seconds with elapsed time
                if elapsed - last_update >= 5:
                    elapsed_str = str(timedelta(seconds=int(elapsed)))
                    if audio_duration:
                        duration_min = audio_duration / 60
                        progress.update(
                            task,
                            description=f"[cyan]Transcribing audio... ({elapsed_str} elapsed, ~{duration_min:.1f} min audio)",
                        )
                    else:
                        progress.update(
                            task,
                            description=f"[cyan]Transcribing audio... ({elapsed_str} elapsed)",
                        )
                    last_update = elapsed
                time.sleep(0.5)

            # Wait for threads to finish reading remaining output
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)

            return_code = process.returncode

            # Final update
            elapsed = time.time() - start_time
            elapsed_str = str(timedelta(seconds=int(elapsed)))
            progress.update(
                task, description=f"[green]✅ Transcription completed in {elapsed_str}"
            )

        # Create result object similar to subprocess.run
        result = type(
            "Result",
            (),
            {
                "returncode": return_code,
                "stdout": "".join(stdout_lines),
                "stderr": "".join(stderr_lines),
            },
        )()

        # Check return code
        if result.returncode != 0:
            # Command failed
            stderr_output = result.stderr if result.stderr else ""
            stdout_output = result.stdout if result.stdout else ""
            console.print(
                f"[red]❌ WhisperX transcription failed (exit code: {result.returncode})[/red]"
            )

            # Show command that failed (without token)
            safe_cmd = [arg if arg != hf_token else "***" for arg in whisperx_cmd]
            console.print(f"[dim]Failed command: {' '.join(safe_cmd)}[/dim]")

            # Show output
            if stdout_output:
                console.print(f"[yellow]STDOUT:[/yellow]")
                console.print(f"{stdout_output}")
            if stderr_output:
                console.print(f"[red]STDERR:[/red]")
                console.print(f"{stderr_output}")

            # If no output, provide helpful message
            if not stdout_output and not stderr_output:
                console.print(
                    f"[yellow]No error output available. Container may have crashed or timed out.[/yellow]"
                )
                console.print(
                    f"[dim]Check logs: docker logs {WHISPERX_CONTAINER_NAME}[/dim]"
                )

            return None

        # Success - show output
        if result.stdout:
            console.print(result.stdout)
        if result.stderr:
            console.print(f"[dim]{result.stderr}[/dim]")

        # Look for the output file in the transcripts directory
        if not DIARISED_TRANSCRIPTS_DIR:
            console.print("[red]Error: DIARISED_TRANSCRIPTS_DIR is not set[/red]")
            return None
        output_dir = Path(DIARISED_TRANSCRIPTS_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get base name without extension for matching
        base_name = audio_file_path.stem
        audio_base_name = Path(audio_file_name).stem

        # Try multiple possible filenames that WhisperX might create
        possible_names = [
            f"{base_name}.json",
            f"{audio_base_name}.json",
            f"{audio_file_name.rsplit('.', 1)[0]}.json",
        ]

        # Check for exact matches first
        for name in possible_names:
            candidate = output_dir / name
            if candidate.exists():
                console.print(f"[green]✅ Transcription completed![/green]")
                return str(candidate)

        # If no exact match, search for files that start with the base name
        matching_files = []
        if output_dir.exists():
            for json_file in output_dir.glob("*.json"):
                file_stem = json_file.stem
                # Check if the file stem matches or starts with our base name
                if (
                    file_stem == base_name
                    or file_stem == audio_base_name
                    or file_stem.startswith(base_name)
                    or file_stem.startswith(audio_base_name)
                ):
                    matching_files.append(json_file)

        # If we found matching files, use the most recently modified one
        if matching_files:
            most_recent = max(matching_files, key=lambda p: p.stat().st_mtime)
            console.print(f"[green]✅ Transcription completed![/green]")
            return str(most_recent)

        # Search for recently created JSON files (created in last 5 minutes)
        current_time = time.time()
        recent_json_files = []
        if output_dir.exists():
            for json_file in output_dir.glob("*.json"):
                try:
                    file_mtime = json_file.stat().st_mtime
                    # Check if file was created in the last 5 minutes
                    if current_time - file_mtime < 300:
                        recent_json_files.append(json_file)
                except OSError:
                    continue

        # If we found recently created files, use the most recently modified one
        if recent_json_files:
            most_recent = max(recent_json_files, key=lambda p: p.stat().st_mtime)
            console.print(f"[green]✅ Transcription completed![/green]")
            return str(most_recent)

        # If still not found, check container output directory directly
        find_cmd = [
            "docker",
            "exec",
            WHISPERX_CONTAINER_NAME,
            "sh",
            "-c",
            "ls -t /data/output/*.json 2>/dev/null | head -1",
        ]
        try:
            find_result = subprocess.run(
                find_cmd, capture_output=True, text=True, check=True, timeout=10
            )
            if find_result.stdout and find_result.stdout.strip():
                container_file = find_result.stdout.strip()
                container_filename = Path(container_file).name
                # Check if it exists on the host
                host_file = output_dir / container_filename
                if host_file.exists():
                    console.print(f"[green]✅ Transcription completed![/green]")
                    return str(host_file)
        except Exception as e:
            console.print(f"[dim]Could not find files in container: {e}[/dim]")

        # File not found
        console.print(
            f"[yellow]Warning: No transcript file found at expected location[/yellow]"
        )
        console.print(f"[dim]Searched for: {possible_names}[/dim]")
        console.print(
            f"[dim]Output directory contents: {[f.name for f in output_dir.glob('*')] if output_dir.exists() else 'Directory does not exist'}[/dim]"
        )
        return None

    except Exception as e:
        import traceback

        console.print(f"[red]Error running WhisperX via Docker Compose: {e}[/red]")
        console.print(f"[dim]Full traceback:[/dim]")
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return None


def run_whisperx_docker(audio_file_path, config=None):
    """
    Run WhisperX transcription in a Docker container using config options.
    This is the original implementation for backward compatibility.
    """
    output_dir = DIARISED_TRANSCRIPTS_DIR
    audio_file_name = os.path.basename(str(audio_file_path))
    # Use config or smart defaults
    model = (
        getattr(config.transcription, "model_name", "large-v2")
        if config
        else "large-v2"
    )
    language = getattr(config.transcription, "language", "en") if config else "en"
    compute_type = (
        getattr(config.transcription, "compute_type", "float32")
        if config
        else "float32"
    )
    diarize = getattr(config.transcription, "diarize", True) if config else True
    min_speakers = getattr(config.transcription, "min_speakers", 1) if config else 1
    max_speakers = getattr(config.transcription, "max_speakers", None) if config else None
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
        hf_token = os.getenv("TRANSCRIPTX_HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN") or ""
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
            "[red]Hugging Face token required for diarization.[/red]"
        )
        console.print(
            "[dim]Set TRANSCRIPTX_HUGGINGFACE_TOKEN or HF_TOKEN "
            "(or transcription.huggingface_token) before running.[/dim]"
        )
        return None
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
        "--language",
        language,
        "--compute_type",
        compute_type,
        "--device",
        device,
    ]
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


def check_whisperx_compose_service():
    """
    Check if the WhisperX Docker Compose container is running and ready.

    Returns:
        bool: True if the container is running (not restarting), False otherwise
    """
    return _check_whisperx_compose_service_core()


def wait_for_whisperx_service(timeout=60, check_interval=2):
    """
    Wait for the WhisperX Docker Compose container to be ready.
    Tests readiness by attempting a simple exec command and verifies stability.

    Args:
        timeout: Maximum time to wait in seconds (default: 60)
        check_interval: Time between checks in seconds (default: 2)

    Returns:
        bool: True if container is ready and stable, False if timeout exceeded
    """
    console = Console()
    start_time = time.time()
    last_status = None
    stable_count = 0
    required_stable_checks = 2  # Container must be stable for 2 consecutive checks

    while time.time() - start_time < timeout:
        # First check if container is running (not restarting)
        if not check_whisperx_compose_service():
            # Container not ready yet, check status
            try:
                result = subprocess.run(
                    [
                        "docker",
                        "ps",
                        "-a",
                        "--filter",
                        f"name={WHISPERX_CONTAINER_NAME}",
                        "--format",
                        "{{.Status}}",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                status = result.stdout.strip()

                if "restarting" in status.lower():
                    elapsed = int(time.time() - start_time)
                    console.print(
                        f"[yellow]⏳ Container is restarting... ({elapsed}s)[/yellow]",
                        end="\r",
                    )
                    stable_count = 0  # Reset stability counter
                elif status:
                    elapsed = int(time.time() - start_time)
                    console.print(
                        f"[cyan]⏳ Waiting for container... ({elapsed}s)[/cyan]",
                        end="\r",
                    )
                    stable_count = 0
            except Exception:
                pass

            time.sleep(check_interval)
            continue

        # Container appears to be running, test if we can actually exec into it
        try:
            test_result = subprocess.run(
                ["docker", "exec", WHISPERX_CONTAINER_NAME, "bash", "-c", "echo ready"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )

            if test_result.returncode == 0 and "ready" in test_result.stdout:
                # Exec works, check if status state (not full status with uptime) is stable
                # Extract just the state part (e.g., "Up" from "Up 2 minutes")
                current_status_full = subprocess.run(
                    [
                        "docker",
                        "ps",
                        "--filter",
                        f"name={WHISPERX_CONTAINER_NAME}",
                        "--format",
                        "{{.Status}}",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                ).stdout.strip()

                # Extract just the state (first word before space)
                current_status = (
                    current_status_full.split()[0] if current_status_full else ""
                )

                if current_status == last_status:
                    stable_count += 1
                    if stable_count >= required_stable_checks:
                        console.print()  # New line after status updates
                        return True
                else:
                    stable_count = 0
                    last_status = current_status
        except subprocess.TimeoutExpired:
            # Exec timed out, container might still be starting
            stable_count = 0
        except Exception:
            # Exec failed, container not ready
            stable_count = 0

        # Not ready yet, show status
        elapsed = int(time.time() - start_time)
        console.print(
            f"[cyan]⏳ Waiting for container to be ready... ({elapsed}s)[/cyan]",
            end="\r",
        )
        time.sleep(check_interval)

    console.print()  # New line after status updates
    return False


def start_whisperx_compose_service():
    """
    Start the WhisperX Docker Compose service.
    CLI wrapper with user-friendly output.

    Returns:
        bool: True if the service started successfully, False otherwise
    """
    console = Console()

    # Call core function
    success = _start_whisperx_compose_service_core()

    if success:
        console.print(
            "[green]✅ WhisperX Docker Compose service started successfully![/green]"
        )
        # Wait for the container to be ready (test with exec)
        console.print("[cyan]Waiting for container to be ready...[/cyan]")
        if wait_for_whisperx_service(timeout=60):
            console.print("[green]✅ Container is ready![/green]")
            return True
        else:
            console.print(
                "[red]❌ Container did not become ready within timeout.[/red]"
            )
            console.print(
                "[yellow]Please check container logs: docker logs transcriptx-whisperx[/yellow]"
            )
            return False
    else:
        console.print("[red]❌ Failed to start WhisperX service.[/red]")
        return False
