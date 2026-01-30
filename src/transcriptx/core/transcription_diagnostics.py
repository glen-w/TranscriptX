"""
Diagnostics helpers for WhisperX transcription.
"""

from __future__ import annotations

from typing import Optional, Tuple

from transcriptx.core.transcription_runtime import WHISPERX_CONTAINER_NAME


def check_model_loading_error(stderr: str) -> Tuple[bool, Optional[str]]:
    """
    Check if stderr contains model loading errors.

    Args:
        stderr: Standard error output from WhisperX

    Returns:
        Tuple of (is_model_error, error_type)
        error_type can be: "ssl_error", "missing_model", "cache_corrupt", or None
    """
    if not stderr:
        return False, None

    stderr_lower = stderr.lower()

    # Check for SSL errors
    if (
        "sslerror" in stderr_lower
        or "ssl error" in stderr_lower
        or "eof occurred in violation of protocol" in stderr_lower
    ):
        return True, "ssl_error"

    # Check for missing model file
    if (
        "unable to open file 'model.bin'" in stderr_lower
        or "model.bin" in stderr_lower
        and "not found" in stderr_lower
    ):
        return True, "missing_model"

    # Check for cache corruption
    if "cache" in stderr_lower and (
        "corrupt" in stderr_lower or "invalid" in stderr_lower
    ):
        return True, "cache_corrupt"

    # Check for Hugging Face sync errors
    if (
        "error occured while synchronizing the model" in stderr_lower
        or "maxretryerror" in stderr_lower
    ):
        return True, "download_error"

    return False, None


def get_model_error_diagnostics(error_type: str, model: str) -> str:
    """
    Get diagnostic steps for model loading errors.

    Args:
        error_type: Type of error ("ssl_error", "missing_model", "cache_corrupt", "download_error")
        model: Model name being used

    Returns:
        Diagnostic message with recovery steps
    """
    cache_dir = "./transcriptx_data/huggingface_cache"
    container_cache = "/root/.cache/huggingface"

    diagnostics = {
        "ssl_error": f"""
SSL/Network Error: Unable to download model from Hugging Face Hub.

Recovery steps:
  1. Check your internet connection
  2. Verify Hugging Face Hub is accessible: curl -I https://huggingface.co
  3. Check if proxy/firewall is blocking connections
  4. Try clearing cache and re-downloading:
     - docker exec {WHISPERX_CONTAINER_NAME} rm -rf {container_cache}/*
     - Restart container: docker restart {WHISPERX_CONTAINER_NAME}
  5. If using a corporate network, check SSL certificate settings
""",
        "missing_model": f"""
Model file missing: The model '{model}' cache is incomplete or corrupted.

Recovery steps:
  1. Clear the model cache:
     - docker exec {WHISPERX_CONTAINER_NAME} rm -rf {container_cache}/hub/models--*
     - Or delete local cache: rm -rf {cache_dir}/hub/models--*
  2. Restart the container to trigger re-download:
     - docker restart {WHISPERX_CONTAINER_NAME}
  3. Verify cache directory is mounted correctly:
     - Check docker-compose.whisperx.yml has volume mount for {cache_dir}
  4. Check disk space: docker exec {WHISPERX_CONTAINER_NAME} df -h {container_cache}
""",
        "cache_corrupt": f"""
Model cache corruption detected.

Recovery steps:
  1. Clear corrupted cache:
     - docker exec {WHISPERX_CONTAINER_NAME} rm -rf {container_cache}/*
     - Or delete local cache: rm -rf {cache_dir}/*
  2. Restart container: docker restart {WHISPERX_CONTAINER_NAME}
  3. Verify cache directory permissions:
     - docker exec {WHISPERX_CONTAINER_NAME} ls -la {container_cache}
""",
        "download_error": f"""
Model download failed from Hugging Face Hub.

Recovery steps:
  1. Check network connectivity:
     - docker exec {WHISPERX_CONTAINER_NAME} ping -c 3 huggingface.co
  2. Verify Hugging Face token is valid (check HF_TOKEN in docker-compose.whisperx.yml)
  3. Clear cache and retry:
     - docker exec {WHISPERX_CONTAINER_NAME} rm -rf {container_cache}/hub/models--*
  4. Check container logs for detailed errors:
     - docker logs {WHISPERX_CONTAINER_NAME}
  5. Try restarting container: docker restart {WHISPERX_CONTAINER_NAME}
""",
    }

    return diagnostics.get(
        error_type, "Unknown model loading error. Check container logs for details."
    )
