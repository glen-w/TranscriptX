"""
Core transcription utilities for WhisperX Docker integration.

This module provides transcription functionality that can be used by both
CLI and GUI without creating circular dependencies.
"""

import json
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Protocol, Tuple
from uuid import uuid4

from transcriptx.core.utils.paths import RECORDINGS_DIR, DIARISED_TRANSCRIPTS_DIR
from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.performance_logger import TimedJob
from transcriptx.core.utils.performance_estimator import (
    PerformanceEstimator,
    format_time_estimate,
)
from transcriptx.core.utils.transcript_languages import (
    ensure_parent_dir,
    get_transcript_path_for_language,
)
from transcriptx.core.transcription_runtime import (
    ContainerRuntime,
    DockerCliRuntime,
    WHISPERX_CONTAINER_NAME,
    check_container_responsive,
    check_whisperx_compose_service,
    start_whisperx_compose_service,
)
from transcriptx.core.transcription_diagnostics import (
    check_model_loading_error,
    get_model_error_diagnostics,
)


class TranscriptionErrorCode(str, Enum):
    INVALID_INPUT = "invalid_input"
    MISSING_CONFIG = "missing_config"
    SERVICE_UNAVAILABLE = "service_unavailable"
    CONTAINER_UNRESPONSIVE = "container_unresponsive"
    MODEL_LOADING_FAILED = "model_loading_failed"
    EXECUTION_FAILED = "execution_failed"
    OUTPUT_MISSING = "output_missing"
    TIMEOUT = "timeout"
    UNEXPECTED_ERROR = "unexpected_error"


@dataclass(frozen=True)
class TranscriptionError:
    code: TranscriptionErrorCode
    message: str
    details: Optional[str] = None


@dataclass(frozen=True)
class WhisperXRunSpec:
    audio_file_path: Path
    target_audio_path: Path
    temp_output_dir: str
    output_dir: Optional[Path]
    model: str
    language: str
    compute_type: str
    diarize: bool
    model_download_policy: str
    hf_token: str
    device: str
    command: list[str]


class AudioMetadataProbe(Protocol):
    def duration_seconds(self, audio_path: Path) -> Optional[float]:
        ...


def _log_transcription_error(
    error: TranscriptionError, *, context: Optional[str] = None
) -> None:
    detail = error.details or context
    log_error("TRANSCRIPTION", f"{error.code.value}: {error.message}", detail)


def verify_model_availability(
    model: str, hf_token: str, max_retries: int = 3
) -> Tuple[bool, Optional[str]]:
    """
    Verify that the WhisperX model is available before transcription.

    This function attempts to check if the model can be loaded by running
    a minimal WhisperX command that will trigger model loading.

    Args:
        model: Model name (e.g., 'large-v2')
        hf_token: Hugging Face token
        max_retries: Maximum number of retry attempts

    Returns:
        Tuple of (is_available, error_message)
        If is_available is True, error_message is None
        If is_available is False, error_message contains diagnostic information
    """
    logger = get_logger()

    if not check_whisperx_compose_service():
        return False, "WhisperX container is not running"

    # Try to verify model by checking cache or running a test command
    # We'll check if model files exist in cache first
    cache_check_cmd = [
        "docker",
        "exec",
        WHISPERX_CONTAINER_NAME,
        "sh",
        "-c",
        "find /root/.cache/huggingface -name 'model.bin' -o -name 'model.safetensors' 2>/dev/null | head -1",
    ]

    try:
        try:
            cache_result = subprocess.run(
                cache_check_cmd, capture_output=True, text=True, timeout=30
            )
        except subprocess.TimeoutExpired:
            logger.debug("Model cache check timed out")
            cache_result = subprocess.CompletedProcess(
                cache_check_cmd, 1, "", "Command timed out"
            )
        if cache_result.stdout and cache_result.stdout.strip():
            logger.debug(f"Model cache found: {cache_result.stdout.strip()}")
            # Cache exists, but we still need to verify it's complete
            # The actual verification will happen during transcription
            return True, None
    except Exception as e:
        logger.debug(f"Could not check model cache: {e}")

    # If no cache found, model will be downloaded during first transcription
    # This is acceptable, so we return True
    logger.debug("No model cache found, will be downloaded on first use")
    return True, None


def _build_whisperx_run_spec(
    audio_file_path: Path, config=None, *, device: str = "cpu"
) -> WhisperXRunSpec:
    audio_file_name = audio_file_path.name
    # Use config or smart defaults
    if config and hasattr(config, "transcription"):
        model = getattr(config.transcription, "model_name", "large-v2") or "large-v2"
        language = getattr(config.transcription, "language", "auto") or "auto"
        compute_type = (
            getattr(config.transcription, "compute_type", "float16") or "float16"
        )
        diarize = getattr(config.transcription, "diarize", True)
        model_download_policy = (
            getattr(config.transcription, "model_download_policy", "anonymous")
            or "anonymous"
        )
        hf_token = getattr(config.transcription, "huggingface_token", "") or ""
    else:
        model = "large-v2"
        language = "auto"
        compute_type = "float16"
        diarize = True
        model_download_policy = "anonymous"
        hf_token = ""

    # If diarization is requested but no HF token is configured, proceed without diarization.
    # WhisperX diarization relies on gated models (e.g., pyannote) which require authentication.
    if diarize and not hf_token:
        get_logger().warning(
            "Diarization requested but no Hugging Face token is configured; "
            "proceeding without diarization. "
            "To enable diarization, set TRANSCRIPTX_HUGGINGFACE_TOKEN or HF_TOKEN "
            "(or transcription.huggingface_token)."
        )
        diarize = False

    # Auto-adjust compute_type for CPU: float16 is not supported on CPU
    if device == "cpu" and compute_type == "float16":
        get_logger().warning("float16 is not supported on CPU. Switching to float32.")
        compute_type = "float32"

    temp_output_dir = "/tmp/whisperx_output"
    output_dir = Path(DIARISED_TRANSCRIPTS_DIR) if DIARISED_TRANSCRIPTS_DIR else None

    # Build a safe shell command for `docker exec ... sh -c "<cmd>"`.
    # Important: `mkdir` must be a separate command (use `&&`), otherwise WhisperX
    # args like `--output_dir` get interpreted as mkdir flags.
    cmd_parts = [
        f"mkdir -p {shlex.quote(temp_output_dir)}",
        "&&",
        "whisperx",
        shlex.quote(f"/data/input/{audio_file_name}"),
        "--output_dir",
        shlex.quote(temp_output_dir),
        "--output_format",
        "json",
        "--model",
        shlex.quote(str(model)),
    ]
    if language and str(language).lower() not in ("auto", "none", ""):
        cmd_parts.extend(["--language", shlex.quote(str(language))])
    cmd_parts.extend(["--compute_type", shlex.quote(str(compute_type))])
    cmd_parts.extend(["--device", shlex.quote(str(device))])
    if hf_token:
        cmd_parts.extend(["--hf_token", shlex.quote(str(hf_token))])
    if diarize:
        cmd_parts.append("--diarize")

    whisperx_cmd = [
        "docker",
        "exec",
        WHISPERX_CONTAINER_NAME,
        "sh",
        "-c",
        " ".join(cmd_parts),
    ]

    recordings_dir = Path(RECORDINGS_DIR) if RECORDINGS_DIR else None
    target_audio_path = (
        recordings_dir / audio_file_name if recordings_dir else audio_file_path
    )

    return WhisperXRunSpec(
        audio_file_path=audio_file_path,
        target_audio_path=target_audio_path,
        temp_output_dir=temp_output_dir,
        output_dir=output_dir,
        model=model,
        language=language,
        compute_type=compute_type,
        diarize=diarize,
        model_download_policy=model_download_policy,
        hf_token=hf_token,
        device=device,
        command=whisperx_cmd,
    )


def run_whisperx_compose(
    audio_file_path: Path,
    config=None,
    audio_probe: Optional[AudioMetadataProbe] = None,
    runtime: Optional[ContainerRuntime] = None,
) -> Optional[str]:
    """
    Run WhisperX transcription using the Docker Compose container.
    This uses docker exec on the running compose container.

    Args:
        audio_file_path: Path to the audio file to transcribe
        config: Optional config object with transcription settings
        audio_probe: Optional metadata probe for duration estimation

    Returns:
        Path to the transcript file if successful, None otherwise
    """
    # Ensure audio_file_path is a Path object
    try:
        audio_file_path = Path(audio_file_path)
    except (TypeError, ValueError) as e:
        _log_transcription_error(
            TranscriptionError(
                code=TranscriptionErrorCode.INVALID_INPUT,
                message=f"Invalid audio file path: {audio_file_path}",
                details=str(e),
            )
        )
        return None

    audio_file_name = audio_file_path.name
    if not audio_file_name:
        _log_transcription_error(
            TranscriptionError(
                code=TranscriptionErrorCode.INVALID_INPUT,
                message=f"Audio file path has no filename: {audio_file_path}",
            )
        )
        return None

    runtime = runtime or DockerCliRuntime()
    spec = _build_whisperx_run_spec(audio_file_path, config)
    model = spec.model
    language = spec.language
    compute_type = spec.compute_type
    diarize = spec.diarize
    model_download_policy = spec.model_download_policy
    hf_token = spec.hf_token
    device = spec.device

    if not model or not compute_type or not device:
        _log_transcription_error(
            TranscriptionError(
                code=TranscriptionErrorCode.MISSING_CONFIG,
                message="Missing required WhisperX configuration parameters",
                details=(
                    f"model={model}, language={language}, compute_type={compute_type}, "
                    f"device={device}"
                ),
            )
        )
        return None

    if model_download_policy == "require_token" and not hf_token:
        _log_transcription_error(
            TranscriptionError(
                code=TranscriptionErrorCode.MISSING_CONFIG,
                message="Hugging Face token required to download models",
                details=(
                    "Set TRANSCRIPTX_HUGGINGFACE_TOKEN or HF_TOKEN "
                    "(or transcription.huggingface_token), or switch "
                    "transcription.model_download_policy to 'anonymous'."
                ),
            )
        )
        return None
    if model_download_policy == "anonymous" and not hf_token:
        get_logger().warning(
            "Proceeding without Hugging Face token (model_download_policy=anonymous). "
            "Downloads may be rate-limited."
        )

    # Ensure the audio file exists
    if not audio_file_path.exists():
        _log_transcription_error(
            TranscriptionError(
                code=TranscriptionErrorCode.INVALID_INPUT,
                message=f"Audio file does not exist: {audio_file_path}",
            )
        )
        return None

    # Ensure the audio file is in the recordings directory (mounted as /data/input)
    if not RECORDINGS_DIR:
        _log_transcription_error(
            TranscriptionError(
                code=TranscriptionErrorCode.MISSING_CONFIG,
                message="RECORDINGS_DIR is not configured",
            )
        )
        return None
    recordings_dir = Path(RECORDINGS_DIR)
    recordings_dir.mkdir(parents=True, exist_ok=True)

    # Copy audio file to recordings directory if it's not already there
    target_audio_path = spec.target_audio_path
    if (
        not target_audio_path.exists()
        or target_audio_path.resolve() != audio_file_path.resolve()
    ):
        try:
            shutil.copy2(audio_file_path, target_audio_path)
            get_logger().debug(
                f"Copied audio file to recordings directory: {target_audio_path}"
            )
        except Exception as e:
            _log_transcription_error(
                TranscriptionError(
                    code=TranscriptionErrorCode.EXECUTION_FAILED,
                    message=(
                        "Failed to copy audio file to recordings directory: "
                        f"{target_audio_path}"
                    ),
                    details=str(e),
                )
            )
            return None

    # Verify container is running before attempting transcription
    if not check_whisperx_compose_service():
        _log_transcription_error(
            TranscriptionError(
                code=TranscriptionErrorCode.SERVICE_UNAVAILABLE,
                message=(
                    f"WhisperX container '{WHISPERX_CONTAINER_NAME}' is not running"
                ),
            )
        )
        return None

    # Verify the target audio file exists in the mounted directory
    if not target_audio_path.exists():
        _log_transcription_error(
            TranscriptionError(
                code=TranscriptionErrorCode.INVALID_INPUT,
                message=(
                    "Audio file not found in recordings directory: "
                    f"{target_audio_path}"
                ),
            )
        )
        return None

    logger = get_logger()
    logger.info(f"Starting WhisperX transcription for: {audio_file_name}")
    logger.debug(
        f"Model: {model}, Language: {language}, Compute: {compute_type}, Device: {device}, Diarize: {diarize}"
    )

    # Get audio file metadata for logging and estimation
    file_size_mb = None
    audio_duration_seconds = None
    try:
        if target_audio_path.exists():
            file_size_mb = target_audio_path.stat().st_size / (1024 * 1024)
            if audio_probe is not None:
                try:
                    audio_duration_seconds = audio_probe.duration_seconds(target_audio_path)
                except Exception:
                    audio_duration_seconds = None
    except Exception:
        pass

    # Show time estimate if we have duration or file size
    estimate = None
    try:
        estimator = PerformanceEstimator()
        estimate = estimator.estimate_transcription_time(
            audio_duration_seconds=audio_duration_seconds,
            file_size_mb=file_size_mb,
            model=model,
        )
        if estimate.get("estimated_seconds") is not None:
            estimate_str = format_time_estimate(estimate)
            logger.info(f"Estimated transcription time: {estimate_str}")
    except Exception:
        pass  # Don't fail if estimation fails

    # Verify model availability before transcription
    model_available, model_error = verify_model_availability(model, hf_token)
    if not model_available and model_error:
        logger.warning(f"Model verification warning: {model_error}")
        # Continue anyway - model might download during transcription

    # Verify audio file is accessible inside container
    verify_audio_cmd = [
        "docker",
        "exec",
        WHISPERX_CONTAINER_NAME,
        "sh",
        "-c",
        f"test -f /data/input/{audio_file_name} && echo 'found' || echo 'missing'",
    ]
    try:
        try:
            verify_result = runtime.exec(verify_audio_cmd, timeout=30, check=False)
        except subprocess.TimeoutExpired:
            logger.warning("Audio file verification timed out")
            verify_result = subprocess.CompletedProcess(
                verify_audio_cmd, 1, "", "Command timed out"
            )
        if verify_result.stdout and "found" in verify_result.stdout:
            logger.debug(
                f"Audio file verified in container: /data/input/{audio_file_name}"
            )
        else:
            logger.warning(
                f"Audio file may not be accessible in container: {verify_result.stdout}"
            )
    except Exception as e:
        logger.warning(f"Could not verify audio file in container: {e}")

    # Use /tmp as intermediate output location to avoid macOS Docker permission issues
    # with listing mounted directories. We'll copy the file to /data/output after transcription.
    temp_output_dir = spec.temp_output_dir
    whisperx_cmd = spec.command

    # Wrap transcription execution with performance logging
    result = None
    try:
        with TimedJob("transcribe.whisperx", audio_file_name) as job:
            job.add_metadata(
                {
                    "model": model,
                    "language": language,
                    "compute_type": compute_type,
                    "device": device,
                    "diarize": diarize,
                }
            )
            if file_size_mb is not None:
                job.add_metadata({"file_size_mb": round(file_size_mb, 2)})
            if audio_duration_seconds is not None:
                job.add_metadata(
                    {"audio_duration_seconds": round(audio_duration_seconds, 2)}
                )

            logger.debug(f"Running WhisperX command: {' '.join(whisperx_cmd)}")
            # Don't use check=True - we want to handle return codes manually
            result = runtime.exec(whisperx_cmd, check=False)

        # Log stdout and stderr regardless of return code
        if result.stdout:
            logger.info(f"WhisperX stdout: {result.stdout}")
        if result.stderr:
            logger.warning(f"WhisperX stderr: {result.stderr}")

        # Check if WhisperX actually succeeded
        if result.returncode != 0:
            # Check for model loading errors specifically
            is_model_error, error_type = check_model_loading_error(result.stderr or "")

            if is_model_error and error_type:
                # Provide detailed diagnostics for model errors
                diagnostics = get_model_error_diagnostics(error_type, model)
                error_msg = (
                    f"WhisperX model loading failed (error type: {error_type})\n"
                    f"Model: {model}\n"
                    f"Return code: {result.returncode}\n\n"
                    f"{diagnostics}\n"
                    f"Raw error output:\n"
                    f"Stderr: {result.stderr[:500] if result.stderr else 'None'}\n"
                    f"Stdout: {result.stdout[:500] if result.stdout else 'None'}"
                )
            else:
                # Generic error handling
                error_msg = f"WhisperX failed with return code {result.returncode}"
                if result.stderr:
                    error_msg += f"\nStderr: {result.stderr}"
                if result.stdout:
                    error_msg += f"\nStdout: {result.stdout}"

            log_error("TRANSCRIPTION", error_msg, f"Audio file: {audio_file_path}")
            return None

        # Look for the output file in the transcripts directory (define early for use in copy)
        if spec.output_dir is None:
            _log_transcription_error(
                TranscriptionError(
                    code=TranscriptionErrorCode.MISSING_CONFIG,
                    message="DIARISED_TRANSCRIPTS_DIR is not set",
                )
            )
            return None
        output_dir = spec.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        # Find the output file in the temp directory and copy it to host
        time.sleep(0.5)  # Brief wait for filesystem sync

        # Check if container is responsive before attempting file operations
        if not check_container_responsive():
            logger.warning(
                "Container appears unresponsive. Waiting 5 seconds and retrying..."
            )
            time.sleep(5)
            if not check_container_responsive():
                logger.error(
                    "Container is not responding to commands. "
                    "The transcription may still be in progress. "
                    "Please check container logs: docker logs transcriptx-whisperx"
                )

        # Find JSON files in temp directory
        # Use a more efficient approach: limit search depth and increase timeout
        find_temp_cmd = [
            "docker",
            "exec",
            WHISPERX_CONTAINER_NAME,
            "sh",
            "-c",
            f"find {temp_output_dir} -maxdepth 2 -name '*.json' -type f 2>&1",
        ]
        try:
            find_temp = runtime.exec(find_temp_cmd, timeout=30, check=False)
        except subprocess.TimeoutExpired:
            logger.warning(
                f"Find command timed out. Container may be unresponsive. "
                f"Trying alternative method to locate transcript files."
            )
            # Try a simpler ls command as fallback
            ls_temp_cmd = [
                "docker",
                "exec",
                WHISPERX_CONTAINER_NAME,
                "sh",
                "-c",
                f"ls -1 {temp_output_dir}/*.json 2>/dev/null || echo ''",
            ]
            try:
                ls_result = runtime.exec(ls_temp_cmd, timeout=15, check=False)
                find_temp = ls_result
            except subprocess.TimeoutExpired:
                logger.error(
                    "Container appears unresponsive. Cannot locate transcript files. "
                    "The transcription may still be processing. "
                    "Check container status: docker ps | grep whisperx"
                )
                find_temp = subprocess.CompletedProcess(
                    find_temp_cmd, 1, "", "Command timed out"
                )

        # Log what we found in temp directory
        if find_temp.stdout:
            logger.debug(f"Files found in temp directory: {find_temp.stdout}")
        if find_temp.stderr:
            logger.debug(f"Temp directory search stderr: {find_temp.stderr}")

        # Copy file from temp to host using docker cp (bypasses macOS mount permission issues)
        if find_temp.stdout and find_temp.stdout.strip():
            # Find the file that matches the current audio file being processed
            temp_files = [
                f.strip() for f in find_temp.stdout.strip().split("\n") if f.strip()
            ]
            # Match by audio file base name (without extension)
            audio_base_name = Path(audio_file_name).stem
            matching_temp_file = None

            for temp_file in temp_files:
                temp_filename = Path(temp_file).name
                temp_base_name = Path(temp_filename).stem
                if temp_base_name == audio_base_name:
                    matching_temp_file = temp_file
                    break

            # If no exact match, use the most recently modified file
            if not matching_temp_file and temp_files:
                # Get the most recent file by checking modification time
                most_recent_cmd = [
                    "docker",
                    "exec",
                    WHISPERX_CONTAINER_NAME,
                    "sh",
                    "-c",
                    f"ls -t {temp_output_dir}/*.json 2>/dev/null | head -1",
                ]
                try:
                    most_recent_result = runtime.exec(
                        most_recent_cmd, timeout=30, check=False
                    )
                except subprocess.TimeoutExpired:
                    logger.warning("Most recent file check timed out, using first file")
                    most_recent_result = subprocess.CompletedProcess(
                        most_recent_cmd, 1, "", "Command timed out"
                    )
                if most_recent_result.stdout and most_recent_result.stdout.strip():
                    matching_temp_file = most_recent_result.stdout.strip()
                else:
                    # Fallback to first file if we can't determine most recent
                    matching_temp_file = temp_files[0]

            if matching_temp_file:
                # Get the filename and create target path
                temp_filename = Path(matching_temp_file).name
                base_name = audio_file_path.stem
                # Save with language-aware naming
                host_target_file = get_transcript_path_for_language(base_name, language)
                ensure_parent_dir(host_target_file)

                # Use docker cp to copy directly from container to host (bypasses mount issues)
                try:
                    copy_result = runtime.copy_out(
                        container_path=matching_temp_file,
                        host_path=host_target_file,
                        timeout=60,
                    )
                except subprocess.TimeoutExpired:
                    logger.error(
                        f"Copy command timed out. File may be too large or container unresponsive."
                    )
                    copy_result = subprocess.CompletedProcess(
                        ["docker", "cp", matching_temp_file, str(host_target_file)],
                        1,
                        "",
                        "Command timed out",
                    )

                if copy_result.returncode == 0 and host_target_file.exists():
                    logger.debug(
                        f"Successfully copied transcript from container to {host_target_file}"
                    )

                    # If the copied file matches the current audio file, return it immediately
                    if Path(host_target_file).stem.startswith(
                        Path(audio_file_name).stem
                    ):
                        logger.info(
                            f"Found transcript at: {host_target_file} (copied from temp)"
                        )
                        transcript_path = str(host_target_file)
                        _ensure_transcript_uuid_in_json(transcript_path)
                        return transcript_path
                else:
                    logger.warning(f"Failed to copy transcript: {copy_result.stderr}")
                    if copy_result.stdout:
                        logger.debug(f"Copy command stdout: {copy_result.stdout}")
        else:
            logger.warning(f"No JSON files found in temp directory {temp_output_dir}")
            # Check if temp directory exists
            check_dir_cmd = [
                "docker",
                "exec",
                WHISPERX_CONTAINER_NAME,
                "sh",
                "-c",
                f"test -d {temp_output_dir} && echo 'exists' || echo 'missing'",
            ]
            try:
                dir_check = runtime.exec(check_dir_cmd, timeout=30, check=False)
            except subprocess.TimeoutExpired:
                logger.warning("Directory check timed out")
                dir_check = subprocess.CompletedProcess(
                    check_dir_cmd, 1, "", "Command timed out"
                )
            if dir_check.stdout:
                logger.debug(f"Temp directory check: {dir_check.stdout.strip()}")

        # Get base name without extension for matching
        base_name = audio_file_path.stem
        audio_base_name = Path(audio_file_name).stem

        expected_path = get_transcript_path_for_language(base_name, language)
        search_dirs = [output_dir]
        if expected_path.parent != output_dir:
            search_dirs.append(expected_path.parent)

        # Try multiple possible filenames that WhisperX might create
        possible_names = [
            f"{base_name}.json",
            f"{audio_base_name}.json",
            f"{audio_file_name.rsplit('.', 1)[0]}.json",
        ]

        # Check for exact matches
        base_name = audio_file_path.stem
        if expected_path.exists():
            logger.info(f"Found transcript at: {expected_path}")
            transcript_path = str(expected_path)
            _ensure_transcript_uuid_in_json(transcript_path)
            return transcript_path
        for name in possible_names:
            for search_dir in search_dirs:
                candidate = search_dir / name
                if candidate.exists():
                    logger.info(f"Found transcript at: {candidate}")
                    transcript_path = str(candidate)
                    _ensure_transcript_uuid_in_json(transcript_path)
                    return transcript_path

        # If no exact match, search for files that start with the base name
        matching_files = []
        for search_dir in search_dirs:
            if search_dir.exists():
                for json_file in search_dir.glob("*.json"):
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
                logger.info(f"Found transcript at: {most_recent} (matched by pattern)")
                transcript_path = str(most_recent)
                _ensure_transcript_uuid_in_json(transcript_path)
                return transcript_path

        # Search for recently created JSON files (created in last 5 minutes)
        current_time = time.time()
        recent_json_files = []
        for search_dir in search_dirs:
            if search_dir.exists():
                for json_file in search_dir.glob("*.json"):
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
            logger.info(f"Found transcript at: {most_recent} (recently created file)")
            transcript_path = str(most_recent)
            _ensure_transcript_uuid_in_json(transcript_path)
            return transcript_path

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
                find_cmd, capture_output=True, text=True, check=True, timeout=30
            )
            if find_result.stdout and find_result.stdout.strip():
                container_file = find_result.stdout.strip()
                container_filename = Path(container_file).name
                logger.debug(
                    f"Most recent JSON file in container: {container_filename}"
                )
                # Check if it exists on the host
                host_file = output_dir / container_filename
                if host_file.exists():
                    logger.info(
                        f"Found transcript at: {host_file} (from container listing)"
                    )
                    transcript_path = str(host_file)
                    _ensure_transcript_uuid_in_json(transcript_path)
                    return transcript_path
        except Exception as e:
            logger.debug(f"Could not find files in container: {e}")

        # Log that we couldn't find the output file
        host_files = list(output_dir.glob("*")) if output_dir.exists() else []

        # Build comprehensive error message with WhisperX output
        error_details = [
            f"Expected at: {output_dir} with names like {possible_names}",
            f"Output dir contents: {[f.name for f in host_files] if host_files else 'Directory does not exist or is empty'}",
        ]

        # Include WhisperX output for diagnostics
        if result.stdout:
            error_details.append(f"WhisperX stdout: {result.stdout}")
            logger.debug(f"WhisperX stdout: {result.stdout}")
        if result.stderr:
            error_details.append(f"WhisperX stderr: {result.stderr}")
            logger.debug(f"WhisperX stderr: {result.stderr}")

        # Check container output directory for additional diagnostics
        try:
            container_check_cmd = [
                "docker",
                "exec",
                WHISPERX_CONTAINER_NAME,
                "sh",
                "-c",
                "ls -la /data/output/ 2>&1",
            ]
            try:
                container_check = subprocess.run(
                    container_check_cmd, capture_output=True, text=True, timeout=30
                )
            except subprocess.TimeoutExpired:
                logger.debug("Container check timed out")
                container_check = subprocess.CompletedProcess(
                    container_check_cmd, 1, "", "Command timed out"
                )
            if container_check.stdout:
                error_details.append(
                    f"Container /data/output listing: {container_check.stdout}"
                )
                logger.debug(
                    f"Container /data/output listing: {container_check.stdout}"
                )
        except Exception as e:
            logger.debug(f"Could not check container output directory: {e}")

        # Try to get recent container logs for additional context
        try:
            logs_cmd = ["docker", "logs", "--tail", "50", WHISPERX_CONTAINER_NAME]
            try:
                logs_result = subprocess.run(
                    logs_cmd, capture_output=True, text=True, timeout=30
                )
            except subprocess.TimeoutExpired:
                logger.debug("Log retrieval timed out")
                logs_result = subprocess.CompletedProcess(
                    logs_cmd, 1, "", "Command timed out"
                )
            if logs_result.stdout:
                # Only include last 20 lines to avoid overwhelming the error message
                log_lines = logs_result.stdout.strip().split("\n")
                recent_logs = "\n".join(log_lines[-20:])
                error_details.append(
                    f"Recent container logs (last 20 lines): {recent_logs}"
                )
                logger.debug(f"Container logs: {recent_logs}")
        except Exception as e:
            logger.debug(f"Could not retrieve container logs: {e}")

        error_msg = "WhisperX completed but transcript file not found. " + " | ".join(
            error_details
        )
        log_error("TRANSCRIPTION", error_msg, f"Audio file: {audio_file_path}")
        return None
    except subprocess.TimeoutExpired as e:
        # Handle timeout errors specifically
        error_msg = (
            f"WhisperX transcription timed out. "
            f"The container may be unresponsive or the transcription is taking longer than expected. "
            f"Command: {e.cmd if hasattr(e, 'cmd') else 'unknown'}, "
            f"Timeout: {e.timeout if hasattr(e, 'timeout') else 'unknown'} seconds. "
            f"Check container status: docker ps | grep whisperx. "
            f"Check container logs: docker logs {WHISPERX_CONTAINER_NAME}"
        )
        log_error("TRANSCRIPTION", error_msg, f"Audio file: {audio_file_path}")
        return None
    except subprocess.CalledProcessError as e:
        # Capture and log the actual error from WhisperX
        error_msg = f"WhisperX subprocess failed with return code {e.returncode}"
        if e.stderr:
            error_msg += f"\nStderr: {e.stderr}"
        if e.stdout:
            error_msg += f"\nStdout: {e.stdout}"

        log_error("TRANSCRIPTION", error_msg, f"Audio file: {audio_file_path}")
        logger.debug(f"Full command: {' '.join(whisperx_cmd)}")
        return None
    except Exception as e:
        log_error(
            "TRANSCRIPTION",
            f"Unexpected error during WhisperX transcription: {e}",
            f"Audio file: {audio_file_path}",
            exception=e,
        )
        return None


def _save_transcript_copy(
    transcript_path: str, audio_file_path: Path, config=None
) -> None:
    """
    Save a copy of the transcript to data/transcripts/ with standardized naming.

    This function creates a copy of the transcript with the naming pattern
    {base_name}.json for English/auto or {base_name}_{lang}.json in a language
    subfolder for non-English.

    Args:
        transcript_path: Path to the transcript JSON file
        audio_file_path: Path to the original audio file
        config: Configuration object (optional)
    """
    try:
        # Check if diarization was enabled
        config_obj = config or get_config()
        diarize = (
            getattr(config_obj.transcription, "diarize", True)
            if config_obj and hasattr(config_obj, "transcription")
            else True
        )

        if not diarize:
            # Only save copy if diarization was enabled
            return

        transcript_file = Path(transcript_path)
        if not transcript_file.exists():
            logger = get_logger()
            logger.warning(f"Transcript file not found for copying: {transcript_path}")
            return

        # Get base name from audio file
        base_name = audio_file_path.stem

        # Create target path with standardized naming
        language = getattr(config_obj.transcription, "language", None)
        target_path = get_transcript_path_for_language(base_name, language)
        ensure_parent_dir(target_path)

        # Copy the transcript file
        shutil.copy2(transcript_file, target_path)
        logger = get_logger()
        logger.info(f"Saved transcript copy to: {target_path}")

    except Exception as e:
        # Log warning but don't raise - transcription should continue even if copy fails
        logger = get_logger()
        logger.warning(f"⚠️ Failed to save transcript copy: {e}")


def _ensure_transcript_uuid_in_json(transcript_path: str) -> Optional[str]:
    """
    Ensure transcript JSON contains a stable transcript_uuid.

    This is intentionally DB-free to keep WhisperX transcription a pure
    JSON creation step.
    """
    try:
        with open(transcript_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError) as e:
        get_logger().warning(f"⚠️ Failed to read transcript JSON: {e}")
        return None

    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    transcript_uuid = metadata.get("transcript_uuid") or data.get("transcript_uuid")
    if transcript_uuid:
        return str(transcript_uuid)

    transcript_uuid = str(uuid4())
    metadata["transcript_uuid"] = transcript_uuid
    data["metadata"] = metadata

    try:
        with open(transcript_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
    except OSError as e:
        get_logger().warning(f"⚠️ Failed to write transcript UUID: {e}")

    return transcript_uuid
