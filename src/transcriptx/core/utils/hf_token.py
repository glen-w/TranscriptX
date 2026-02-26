"""
Centralized resolution of the Hugging Face token for TranscriptX.

Precedence: config.transcription.huggingface_token, TRANSCRIPTX_HUGGINGFACE_TOKEN,
HF_TOKEN, then TRANSCRIPTX_HUGGINGFACE_TOKEN_FILE / HF_TOKEN_FILE (read path, strip, validate).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def resolve_hf_token(config: Any = None) -> str:
    """
    Return the effective Hugging Face token with unified precedence.

    Order: config.transcription.huggingface_token (if non-empty), env
    TRANSCRIPTX_HUGGINGFACE_TOKEN, env HF_TOKEN, then read from file path given by
    TRANSCRIPTX_HUGGINGFACE_TOKEN_FILE or HF_TOKEN_FILE (strip whitespace/newlines;
    warn if non-empty and token does not start with "hf_").

    Args:
        config: Optional TranscriptX config object with transcription.huggingface_token.

    Returns:
        The resolved token string (may be empty).
    """
    # 1. Config
    if config is not None and hasattr(config, "transcription"):
        token = getattr(config.transcription, "huggingface_token", "") or ""
        if isinstance(token, str) and token.strip():
            return token.strip()

    # 2. Env TRANSCRIPTX_HUGGINGFACE_TOKEN
    token = os.getenv("TRANSCRIPTX_HUGGINGFACE_TOKEN") or ""
    if token.strip():
        return token.strip()

    # 3. Env HF_TOKEN
    token = os.getenv("HF_TOKEN") or ""
    if token.strip():
        return token.strip()

    # 4. *_FILE convention
    for env_key in ("TRANSCRIPTX_HUGGINGFACE_TOKEN_FILE", "HF_TOKEN_FILE"):
        path_str = os.getenv(env_key)
        if not path_str or not path_str.strip():
            continue
        path = Path(path_str.strip())
        if not path.exists():
            continue
        try:
            raw = path.read_text(encoding="utf-8")
            token = raw.strip()
            if not token:
                continue
            if not token.startswith("hf_"):
                logger.warning(
                    "Hugging Face token from %s does not start with 'hf_'; "
                    "it may be invalid or from an older format.",
                    env_key,
                )
            return token
        except OSError as e:
            logger.debug("Could not read %s from %s: %s", env_key, path, e)
            continue

    return ""
